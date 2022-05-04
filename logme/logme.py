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
from logme.ATimeLogger import get_ProcessATimeLoggerApi, ATimeLoggerApi
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


def source_trigger(src: str = None) -> None:
    print(f"src: {src}")
    conf = get_source_conf(src)
    print(f"src config: {src}\n{conf}")
    dst = get_local_storage_path(config.CONFIG_FILE_PATH)
    if src == 'aTimeLogger':
        print('get aTimeLogger data')
        if conf['connection'] == 'GoogleDrive':
            downloader = GoogleDriveDownloader(src, dst)
            return downloader.download(src, dst)
        if conf['connection'] == 'api':
            downloader = ATimeLoggerApi(src, dst)
            # Download json with aTimeLogger api
            downloader.download(src, dst)
            # Process downloaded with pandas
            processor = get_ProcessATimeLoggerApi(dst)
            result = processor.process(dst)
            exit(1)
    elif src == 'duolingo':
        print('get duolingo data')
        exit(1)


class Processor(NamedTuple):
    """Class to process files for the database"""
    data: pd.DataFrame
    error: int


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
