"""This module provides the logme model-controller."""

from .ingestion import (ATimeLoggerIngestor, KoreaderClippingIngest,KoreaderStatistics,Duolingo,Instagram,Multi_TimerIngestor)
from .processing import Multi_TimerProcessor
from .connectors import GoogleDrive
from .connectors import Dropbox
import pandas as pd
from .storage.database import DatabaseHandler
from logme import DB_READ_ERROR, ID_ERROR, creds_dict, SCOPES, CONFIG_FILE_PATH, FILE_ERROR, SUCCESS, config, date_time
import io
import os.path
from os import makedirs
from pathlib import Path
from typing import Any, Dict, List, NamedTuple
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'ingestion'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'connectors'))
import logging
# from .utils.Utils import get_local_storage_path
import logme.utils.Utils as u

logger = logging.getLogger(__name__)


class CurrentLogme(NamedTuple):
    todo: Dict[str, Any]
    error: int

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


def source_trigger(src: str = None) -> None:
    logger.info(f"source_trigger src: {src}")
    dst_path = Path(u.get_local_storage_path(config.CONFIG_FILE_PATH)/"landing"/src/f"{date_time}")
    conf = u.get_source_conf(src)
    match(src):
        case 'aTimeLogger':
            logger.info('get aTimeLogger data')
            if conf['connection'] == 'GoogleDrive':
                downloader = GoogleDrive.GoogleDriveDownloader(src, dst)
                tmp = downloader.download()            
                exit(0)
                return downloader.download(src, dst)
            if conf['connection'] == 'api':
                downloader = ATimeLoggerIngestor.ATimeLoggerApi(src, dst)
                # Download json with aTimeLogger api
                downloader.download()
                # Process downloaded with pandas
            processor = ATimeLoggerIngestor.get_ProcessATimeLoggerApi(dst)
            result = processor.process(src,dst)
        case 'duolingo':
            logger.info(f'Downloading {src}')
            languages_processor = Duolingo.DuolingoApi(src, dst)
            # downloader.process(skills)
        case 'koreaderStatistics':
            logger.info('Process koreader statistic file')
            if conf['connection'] == 'GoogleDrive':
                downloader = GoogleDrive(src, dst)
                # return downloader.download(src, dst)
            if conf['connection'] == 'file_system':
                processor = KoreaderStatistics(src, dst)
                processor.process()
        case 'koreaderClipping':
            logger.info('Process highlighted texts in Koreader')
            processor = KoreaderClippingIngest(src, dst)
            processor.pre_process()
        case 'instagram':
            logger.info('Process instagram saved posts')
            processor = Instagram.InstagramIngest(src, dst)
            processor.instaloader_download(1)
        case "Multi_Timer":
            logger.info('Process Multi_Timer')
            ingestor = Multi_TimerIngestor.MultiTimerIngest(src, dst_path, conf)
            # files_downloaded = ingestor.ingest_to_landing()
            files_downloaded = ['/home/rjof/logme_data/landing/Multi_Timer/2025-04-17_17-44-10/timer_history_2025_04_06.csv']
            logger.info(f'Files downloaded: {files_downloaded}')
            if files_downloaded:
                # ingestor.move_to_history(files_downloaded)
                files_moved = [f.replace("/landing/","/history/") for f in files_downloaded]
                processor = Multi_TimerProcessor.Multi_TimerProcessor(files_moved, conf)
                dfs = processor.landing_to_raw()
                processor.raw_to_l1(dfs)
                exit(2)
        case _:
            logger.info(f"{src} not yet implemented. Check TODO.md file for check the planning.")

class Processor(NamedTuple):
    """Class to process files for the database"""
    data: pd.DataFrame
    error: int
