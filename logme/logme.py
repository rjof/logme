"""This module provides the logme model-controller."""

# from .utils.Utils import get_local_storage_path
# from .ingestion import (
#     ATimeLoggerIngestor,
#     KoreaderClippingIngest,
#     KoreaderStatistics,
#     Duolingo,
#     Instagram,
#     Multi_TimerIngestor,
# )
# from .storage.database import DatabaseHandler
from logme.ingestors.InstagramIngestor import InstagramIngestor
from logme import (
    config,
    date_time,
)
import logme.utils.Utils as u
from logme.processors import Multi_TimerProcessor
from logme.connectors import GoogleDrive
from logme.connectors import Dropbox
import pandas as pd

import io
import os.path
from os import makedirs
from pathlib import Path
from typing import Any, Dict, List, NamedTuple
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "ingestion"))
sys.path.append(os.path.join(os.path.dirname(__file__), "connectors"))
import logging


logger = logging.getLogger(__name__)


def source_trigger(src: str = None) -> None:
    logger.info(f"source_trigger src: {src}")
    dst_path = Path(
        u.get_local_storage_path(config.CONFIG_FILE_PATH)
        / "landing"
        / src
        / f"{date_time}"
    )
    conf = u.get_source_conf(src, src)
    conf_raw_to_l1 = u.get_source_conf(src, f"{src}_raw_to_l1")
    match (src):
        case "aTimeLogger":
            logger.info("get aTimeLogger data")
            if conf["connection"] == "GoogleDrive":
                downloader = GoogleDrive.GoogleDriveDownloader(src, dst)
                tmp = downloader.download()
                exit(0)
                return downloader.download(src, dst)
            if conf["connection"] == "api":
                downloader = ATimeLoggerIngestor.ATimeLoggerApi(src, dst)
                # Download json with aTimeLogger api
                downloader.download()
                # Process downloaded with pandas
            processor = ATimeLoggerIngestor.get_ProcessATimeLoggerApi(dst)
            result = processor.process(src, dst)
        case "duolingo":
            logger.info(f"Downloading {src}")
            languages_processor = Duolingo.DuolingoApi(src, dst)
            # downloader.process(skills)
        case "koreaderStatistics":
            logger.info("Process koreader statistic file")
            if conf["connection"] == "GoogleDrive":
                downloader = GoogleDrive(src, dst)
                # return downloader.download(src, dst)
            if conf["connection"] == "file_system":
                processor = KoreaderStatistics(src, dst)
                processor.process()
        case "koreaderClipping":
            logger.info("Process highlighted texts in Koreader")
            processor = KoreaderClippingIngest(src, dst)
            processor.pre_process()
        case "instagram":
            logger.info("Process instagram saved posts")
            ingestor = InstagramIngestor(src, conf)
            ingestor.instaloader_download(6)
        case "Multi_Timer":
            logger.info("Process Multi_Timer")
            ingestor = Multi_TimerIngestor.MultiTimerIngest(src, dst_path, conf)
            # files_downloaded = ingestor.ingest_to_landing()
            files_downloaded = [
                "/home/rjof/logme_data/landing/Multi_Timer/2025-04-24_00-50-00/timer_history_2025_04_24.csv"
            ]
            logger.info(f"Files downloaded: {files_downloaded}")
            # files_downloaded = u.remove_already_processed(src, files_downloaded)
            # logger.info(f'Files downloaded removing processed: {files_downloaded}')
            if files_downloaded:
                ingestor.move_to_history(files_downloaded)
                files_moved = [
                    f.replace("/landing/", "/history/") for f in files_downloaded
                ]
                processor = Multi_TimerProcessor.Multi_TimerProcessor(files_moved)
                dfs = processor.landing_to_raw()
                dfs = processor.raw_to_l1(dfs)
                dfs = processor.l1_to_l2(dfs)
        case _:
            logger.info(
                f"{src} not yet implemented. Check TODO.md file for check the planning."
            )


class CurrentLogme(NamedTuple):
    todo: Dict[str, Any]
    error: int


class Processor(NamedTuple):
    """Class to process files for the database"""

    data: pd.DataFrame
    error: int
