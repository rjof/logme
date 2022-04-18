"""This module provides the logme model-controller."""
import configparser
import io
import time
from os import makedirs
from pathlib import Path
from typing import Any, Dict, List, NamedTuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from requests.auth import HTTPBasicAuth
from logme import DB_READ_ERROR, ID_ERROR, creds_dict, SCOPES, CONFIG_FILE_PATH, FILE_ERROR, SUCCESS
from logme.database import DatabaseHandler
import requests
from os import environ
from json import load, dump
import pandas as pd
from sqlalchemy import (create_engine, MetaData, Table,
                        Column, Integer, String, sql)


class CurrentLogme(NamedTuple):
    todo: Dict[str, Any]
    error: int


def get_local_storage_path(config_file: Path) -> Path:
    """Return the local path to the downloaded files."""
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file)
    return Path(config_parser["LocalPaths"]["storage"])


def get_source_conf(src: str = None) -> dict:
    config_parser = configparser.ConfigParser()
    config_parser.read(CONFIG_FILE_PATH)
    options = [option for option in config_parser[src]]
    thedict = {}
    for option in options:
        for key, val in config_parser.items(src):
            if key == 'days_to_retrieve_api':
                thedict[key] = float(val)
            else:
                thedict[key] = val
    return thedict


class Processor(NamedTuple):
    """Class to process files for the database"""
    data: pd.DataFrame
    error: int


class ProcessATimeLoggerApi:
    """Class to process aTimeLogger json files"""

    def __init__(self, src: Path, db_path: Path) -> None:
        self.src = src
        self._db_handler = DatabaseHandler(db_path)

    def process(self, src: str = None) -> int:
        # Check files activities.json & intervals.json exists
        input_files = {
            'activities_file': Path(src) / 'aTimeLogger/activities.json',
            'intervals_file': Path(src) / 'aTimeLogger/intervals.json'
        }
        # Load them
        for key in input_files:
            print(f"variable: {key} is {input_files[key]}")
            try:
                with open(input_files[key], 'r') as f:
                    globals()[key] = load(f)
            except FileNotFoundError:
                msg = f"The file {input_files[key]} was not found."
                raise Exception(msg)
        # Clean
        activities = pd.json_normalize(activities_file['types'])
        activities = activities[['guid', 'name', 'group',
                                 'parent']]
        print(f"activities.shape: {activities.shape}")

        intervals = pd.json_normalize(intervals_file['intervals'])
        intervals = intervals[["guid", "from", "to",
                               "comment", "type.guid"]]
        intervals["duration_sec"] = \
            intervals["to"] - intervals["from"]
        print(f"intervals.shape: {intervals.shape}")

        m1 = pd.merge(
            intervals,
            activities,
            right_on="guid",
            left_on="type.guid")[["name","comment","duration_sec",
                                  "from","to","group","parent"]]
        print(f"m1: {m1.shape}")
        m2 = pd.merge(
            m1,
            activities,
            left_on="parent",
            right_on="guid"
        )[["name_y", "name_x","comment","duration_sec","from","to"]]
        m2.rename(columns={'name_y':'in_group',
                           'name_x':'activity',
                           'from':'ts_from',
                           'to':'ts_to'
                           }, inplace=True)
        # Add a hash as index
        m2['hash'] = pd.Series((hash(tuple(row)) for
                                _,
                                row in m2.iterrows()))
        m2 = m2[['hash','in_group', 'activity', 'comment',
                 'duration_sec', 'ts_from', 'ts_to']]
        m2 = m2.sort_values(by="ts_from")
        print(f"m2: {m2.shape}")

        logme_df, err = self._db_handler.load_logme()
        print(f"logme_df: {logme_df.shape}")

        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        logme_df.columns = m2.columns
        merged = m2.merge(logme_df.drop_duplicates(),
                  on=['in_group', 'activity', 'comment',
                      'duration_sec', 'ts_from', 'ts_to'],
                  how='left', indicator=True)
        merged.rename(columns={'hash_x':'hash'}, inplace=True)
        already_saved = merged[merged['_merge']=='both']
        to_save = merged[merged['_merge']!='both']
        to_save = to_save[m2.columns]
        print(f"merged: {merged.shape}")
        print(f"already_saved: {already_saved.shape}")
        print(f"to_save: {to_save.shape}")
        print(f"To be inserted: {to_save.shape}")
        return self._db_handler.write_logme(to_save)


class ATimeLoggerApi:
    """Class to call the aTimeLogger api"""

    def __init__(self, src: str, dst: Path) -> None:
        self.src = src
        self.dst = dst

    def download(self, src: str = None, dst: Path = None) -> int:
        error = 0
        dst_path = Path(dst) / src
        if not dst_path.exists():
            makedirs(dst_path)
        load_dotenv('.env')
        user = environ.get('aTimeLogger_user')
        password = environ.get('aTimeLogger_pass')
        conf = get_source_conf(src)
        from_secs = int(time.time()) - int(conf['days_to_retrieve_api'] * 24 * 60 * 60)
        # Another not useful end point
        # "https://app.atimelogger.com/api/v2/types",
        urls = [
            "https://app.atimelogger.com/api/v2/activities?limit=200",
            f"https://app.atimelogger.com/api/v2/intervals?limit=100&from={from_secs}"
        ]
        for url in urls:
            resp = requests.get(url, auth=HTTPBasicAuth(user, password))
            if not resp.status_code == 200:
                error = 1
                raise Exception("The aTimeLogger api seems to be down... or your request?")
            print(f"{url}: {resp.status_code}")
            dst_file = Path(dst_path) / f"{urlparse(url).path.split('/')[-1]}.json"
            print(f"dst file: {dst_file}")
            with open(dst_file, "w") as f:
                dump(resp.json(), f)
        return error


class GoogleDriveDownloader:
    """Class to download log files from Google Drive."""

    def __init__(self, src: str, dst: Path) -> None:
        self.src = src
        self.dst = dst

    def download(self, src: str, dst: Path) -> int:
        creds = service_account. \
            Credentials. \
            from_service_account_info(creds_dict, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)

        dst_path = Path(dst) / src
        if not dst_path.exists():
            makedirs(dst_path)

        try:
            # Call the Drive v3 API
            results = service.files().list(
                q=f"name contains '{src}'",
                pageSize=30, fields="nextPageToken, "
                                    "files(id, name, modifiedTime, parents)").execute()
            items = results.get('files', [])

            if not items:
                print('No files found.')
                return 1
            print('Files:')
            for item in items:
                print(item)
                request = service.files().get(fileId=item['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print("Download %d%%." % int(status.progress() * 100))
                    dst_file = Path(dst_path) / f"{item['id']}_metadata.txt"
                    with open(dst_file, "wb") as f:
                        f.write(fh.getbuffer())

                    request = service.files().get_media(fileId=item['id'])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        print("Download %d%%." % int(status.progress() * 100))
                    dst_file = Path(dst_path) / f"{item['id']}_file.csv"
                    with open(dst_file, "wb") as f:
                        f.write(fh.getbuffer())
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            print(f'An error occurred: {error}')
        return 1


class Todoer:
    def __init__(self, db_path: Path) -> None:
        self._db_handler = DatabaseHandler(db_path)

    def add(self, description: List[str], priority: int = 2) -> CurrentLogme:
        """Add a new to-do to the database."""
        description_text = " ".join(description)
        if not description_text.endswith("."):
            description_text += "."
        todo = {
            "Description": description_text,
            "Priority": priority,
            "Done": False,
        }
        read = self._db_handler.read_logme()
        if read.error == DB_READ_ERROR:
            return CurrentLogme(todo, read.error)
        read.todo_list.append(todo)
        write = self._db_handler.write_todo(read.todo_list)
        return CurrentLogme(todo, write.error)

    def get_todo_list(self) -> List[Dict[str, Any]]:
        """Return the current to-do list."""
        read = self._db_handler.read_logme()
        return read.todo_list

    def set_done(self, todo_id: int) -> CurrentLogme:
        """Set a to-do as done."""
        read = self._db_handler.read_logme()
        if read.error:
            return CurrentLogme({}, read.error)
        try:
            todo = read.todo_list[todo_id - 1]
        except IndexError:
            return CurrentLogme({}, ID_ERROR)
        todo["Done"] = True
        write = self._db_handler.write_todo(read.todo_list)
        return CurrentLogme(todo, write.error)

    def remove(self, todo_id: int) -> CurrentLogme:
        """Remove a to-do from the database using its id or index."""
        read = self._db_handler.read_logme()
        if read.error:
            return CurrentLogme({}, read.error)
        try:
            todo = read.todo_list.pop(todo_id - 1)
        except IndexError:
            return CurrentLogme({}, ID_ERROR)
        write = self._db_handler.write_todo(read.todo_list)
        return CurrentLogme(todo, write.error)

    def remove_all(self) -> CurrentLogme:
        """Remove all to-dos from the database."""
        write = self._db_handler.write_todo([])
        return CurrentLogme({}, write.error)
