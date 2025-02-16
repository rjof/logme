"""This module provides the logme model-controller."""

from .sources import KoreaderClippingIngest
from .sources import KoreaderStatistics
from .sources import ATimeLogger
from .sources import Duolingo
from .sources import Instagram
import pandas as pd
from logme.database import DatabaseHandler
from logme import DB_READ_ERROR, ID_ERROR, creds_dict, SCOPES, CONFIG_FILE_PATH, FILE_ERROR, SUCCESS
import configparser
import io
import os.path
import shutil
from os import makedirs
from pathlib import Path
from typing import Any, Dict, List, NamedTuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import sys
from logme import config
fpath = os.path.join(os.path.dirname(__file__), 'sources')
sys.path.append(fpath)
import logging

logger = logging.getLogger(__name__)


class CurrentLogme(NamedTuple):
    todo: Dict[str, Any]
    error: int


def move_file_in_local_system(src_file: Path, dst_path: Path):
    logger.info(f"move file: {src_file}")
    dst_file = dst_path / os.path.basename(src_file)
    # source file exists?
    if not src_file.exists():
        return logger.info(f"{src_file} not present")
    # destination file exists?
    if dst_file.is_file():
        # as the dst file exists, get modification time of file
        if os.path.getmtime(src_file) > os.path.getmtime(dst_file):
            shutil.move(src_file, dst_file)
        else:
            msg = f"Source file {src_file} is older than {dst_file}"
            raise Exception(msg)
    else:
        shutil.move(src_file, dst_file)


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
    logger.info(f"src: {src}")
    conf = get_source_conf(src)
    dst = get_local_storage_path(config.CONFIG_FILE_PATH)
    if src == 'aTimeLogger':
        logger.info('get aTimeLogger data')
        if conf['connection'] == 'GoogleDrive':
            downloader = GoogleDriveDownloader(src, dst)
            return downloader.download(src, dst)
        if conf['connection'] == 'api':
            downloader = ATimeLogger.ATimeLoggerApi(src, dst)
            # Download json with aTimeLogger api
            downloader.download()
            # Process downloaded with pandas
            processor = ATimeLogger.get_ProcessATimeLoggerApi(dst)
            result = processor.process(src,dst)
    elif src == 'duolingo':
        logger.info(f'Downloading {src}')
        languages_processor = Duolingo.DuolingoApi(src, dst)
        # downloader.process(skills)
    elif src == 'koreaderStatistics':
        logger.info('Process koreader statistic file')
        if conf['connection'] == 'GoogleDrive':
            downloader = GoogleDriveDownloader(src, dst)
            # return downloader.download(src, dst)
        if conf['connection'] == 'file_system':
            processor = KoreaderStatistics(src, dst)
            processor.process()
    elif src == 'koreaderClipping':
        logger.info('Process highlighted texts in Koreader')
        processor = KoreaderClippingIngest(src, dst)
        processor.pre_process()
    elif src == 'instagram':
        logger.info('Process instagram saved posts')
        processor = Instagram.InstagramIngest(src, dst)
        processor.instaloader_download(1)
    else:
        logger.info(f"{src} not yet implemented. Check TODO.md file for check the planning.")


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
                logger.info('No files found.')
                return 1
            logger.info('Files:')
            for item in items:
                logger.info(item)
                request = service.files().get(fileId=item['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    logger.info("Download %d%%." % int(status.progress() * 100))
                    dst_file = Path(dst_path) / f"{item['id']}_metadata.txt"
                    with open(dst_file, "wb") as f:
                        f.write(fh.getbuffer())

                    request = service.files().get_media(fileId=item['id'])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        logger.info("Download %d%%." % int(status.progress() * 100))
                    dst_file = Path(dst_path) / f"{item['id']}_file.csv"
                    with open(dst_file, "wb") as f:
                        f.write(fh.getbuffer())
        except HttpError as error:
            # TODO(developer) - Handle errors from drive API.
            logger.error(f'An error occurred: {error}')
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
