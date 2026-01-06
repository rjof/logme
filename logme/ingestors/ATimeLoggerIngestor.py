from dotenv import load_dotenv
from json import load, dump
from logme import config, SUCCESS, now, date_time
from logme.utils.Utils import get_database_path
# from logme.storage.database import DatabaseHandler
from os import makedirs
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse
import requests
import typer
from os import environ
from pathlib import Path
import pandas as pd
import time
import logging
import numpy as np


class ProcessATimeLoggerApi:
    """Class to process aTimeLogger json files"""

    def __init__(self, src: Path, db_path: Path) -> None:
        self.src = src
        self._db_handler = DatabaseHandler(db_path)
        self.logger = logging.getLogger(self.__class__.__name__)

    def process(self, srcName: str, src: Path = None) -> int:
        # Check files activities.json & intervals.json exists
        input_files = {
            "activities_file": Path(src) / f"aTimeLogger/{date_time}/activities.json",
            "intervals_file": Path(src) / f"aTimeLogger/{date_time}/intervals.json",
        }

        # Load them
        for key in input_files:
            self.logger.info(f"variable: {key} is {input_files[key]}")
            try:
                with open(input_files[key], "r") as f:
                    globals()[key] = load(f)
            except FileNotFoundError:
                msg = f"The file {input_files[key]} was not found."
                raise Exception(msg)
        # Clean
        activities = pd.json_normalize(activities_file["types"])
        activities = activities[["guid", "name", "group", "parent"]]
        self.logger.info(f"activities.shape: {activities.shape}")

        intervals = pd.json_normalize(intervals_file["intervals"])
        intervals = intervals[["guid", "from", "to", "comment", "type.guid"]]
        intervals["duration_sec"] = intervals["to"] - intervals["from"]
        self.logger.info(f"intervals.shape: {intervals.shape}")

        activities_intervals = pd.merge(
            intervals, activities, right_on="guid", left_on="type.guid"
        )[["name", "comment", "duration_sec", "from", "to", "group", "parent"]]
        self.logger.info(f"activities_intervals: {activities_intervals.shape}")
        self.logger.info(f"activities_intervals: {activities_intervals.columns}")

        activities_intervals_select = pd.merge(
            activities_intervals, activities, left_on="parent", right_on="guid"
        )[["name_y", "name_x", "comment", "duration_sec", "from", "to"]]
        activities_intervals_select.rename(
            columns={
                "name_y": "in_group",
                "name_x": "activity",
                "from": "ts_from",
                "to": "ts_to",
            },
            inplace=True,
        )
        # Add a hash as index
        activities_intervals_select["hash"] = pd.util.hash_pandas_object(
            activities_intervals_select
        )
        # Change type from unit64 to object
        activities_intervals_select["hash"] = activities_intervals_select[
            "hash"
        ].astype(str)
        activities_intervals_select = activities_intervals_select[
            [
                "hash",
                "in_group",
                "activity",
                "comment",
                "duration_sec",
                "ts_from",
                "ts_to",
            ]
        ]
        activities_intervals_select = activities_intervals_select.sort_values(
            by="ts_from"
        )
        self.logger.info(
            f"activities_intervals_select: {activities_intervals_select.shape}"
        )
        self.logger.info(
            f"activities_intervals_select: {activities_intervals_select.columns}"
        )

        logme_df, err = self._db_handler.load_logme()
        logme_df = logme_df[activities_intervals_select.columns]
        self.logger.info(f"logme_df: {logme_df.shape}")
        self.logger.info(f"logme_df: {logme_df.columns}")

        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        logme_df.columns = activities_intervals_select.columns
        merged = activities_intervals_select.merge(
            logme_df.drop_duplicates(),
            on=["in_group", "activity", "comment", "duration_sec", "ts_from", "ts_to"],
            how="left",
            indicator=True,
        )
        merged.rename(columns={"hash_x": "hash"}, inplace=True)
        already_saved = merged[merged["_merge"] == "both"]
        to_save = merged[merged["_merge"] != "both"]
        to_save = to_save[activities_intervals_select.columns]
        self.logger.info(f"to_save: {to_save.shape}")
        self.logger.info(f"to_save: {to_save.columns}")
        num_rows = len(to_save.index)
        ts_added = int(time.mktime(now.timetuple()))
        date_col = np.repeat(ts_added, num_rows)
        src_col = np.repeat(srcName, num_rows)
        to_save["src"] = src_col
        to_save["ts_added"] = date_col
        self.logger.info(f"merged: {merged.shape}")
        self.logger.info(f"already_saved: {already_saved.shape}")
        self.logger.info(f"To be inserted (to_save): {to_save.shape}")
        self.logger.info(f"Some rows: {to_save}")

        return self._db_handler.write_logme(to_save)


class ATimeLoggerApi:
    """Class to call the aTimeLogger api"""

    def __init__(self, src: str, dst: Path) -> None:
        self.src = src
        self.dst = dst
        self.logger = logging.getLogger(self.__class__.__name__)

    def download(self) -> int:
        error = 0
        dst_path = Path(self.dst) / self.src / f"{date_time}"
        if not dst_path.exists():
            makedirs(dst_path)
        load_dotenv(".env")
        user = environ.get("aTimeLogger_user")
        password = environ.get("aTimeLogger_pass")
        conf = logme.get_source_conf(self.src)
        from_secs = int(time.time()) - int(conf["days_to_retrieve_api"] * 24 * 60 * 60)
        # Another not useful end point
        # "https://app.atimelogger.com/api/v2/types",
        # The logic of limit, which is how many activities to download, is to assume
        # that the maximum to downoad is the number of seconds in the interval
        # divided by 5 minutes (300 seconds)
        limit = int(from_secs / 300)
        urls = [
            "https://app.atimelogger.com/api/v2/activities?limit=200",
            f"https://app.atimelogger.com/api/v2/intervals?limit={limit}&from={from_secs}",
        ]
        for url in urls:
            resp = requests.get(url, auth=HTTPBasicAuth(user, password))
            if not resp.status_code == 200:
                error = 1
                raise Exception(
                    "The aTimeLogger api seems to be down... or your request?"
                )
            self.logger.info(f"{url}: {resp.status_code}")
            dst_file = Path(dst_path) / f"{urlparse(url).path.split('/')[-1]}.json"
            self.logger.info(f"dst file: {dst_file}")
            with open(dst_file, "w") as f:
                dump(resp.json(), f)
        return error


def get_ProcessATimeLoggerApi(src: Path) -> ProcessATimeLoggerApi:
    if config.CONFIG_FILE_PATH.exists():
        db_path = get_database_path(config.CONFIG_FILE_PATH)
    else:
        typer.secho(
            'Config file not found. Please, run "logme init"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    if db_path.exists():
        return ProcessATimeLoggerApi(src, db_path)
    else:
        typer.secho(
            'Database not found. Please, run "logme init"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
