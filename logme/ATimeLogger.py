from dotenv import load_dotenv
from json import load, dump
from logme import (config, database, sources, SUCCESS,
                   logme)

from logme.database import DatabaseHandler
from os import makedirs
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse
import requests
import typer
from os import environ
from pathlib import Path
import pandas as pd
import time


class ProcessATimeLoggerApi:
    """Class to process aTimeLogger json files"""

    def __init__(self, src: Path, db_path: Path) -> None:
        self.src = src
        self._db_handler = DatabaseHandler(db_path)

    def process(self, src: Path = None) -> int:
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
        m2.rename(columns={'name_y': 'in_group',
                           'name_x': 'activity',
                           'from': 'ts_from',
                           'to': 'ts_to'
                           }, inplace=True)
        # Add a hash as index
        m2['hash'] = pd.util.hash_pandas_object(m2)
        # Change type from unit64 to object
        m2['hash'] = m2['hash'].astype(str)
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

    def download(self) -> int:
        error = 0
        dst_path = Path(self.dst) / self.src
        if not dst_path.exists():
            makedirs(dst_path)
        load_dotenv('.env')
        user = environ.get('aTimeLogger_user')
        password = environ.get('aTimeLogger_pass')
        conf = logme.get_source_conf(self.src)
        from_secs = int(time.time()) - int(conf['days_to_retrieve_api'] * 24 * 60 * 60)
        # Another not useful end point
        # "https://app.atimelogger.com/api/v2/types",
        urls = [
            "https://app.atimelogger.com/api/v2/activities?limit=200",
            f"https://app.atimelogger.com/api/v2/intervals?limit=1000&from={from_secs}"
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


def get_ProcessATimeLoggerApi(src: Path) -> ProcessATimeLoggerApi:
    if config.CONFIG_FILE_PATH.exists():
        db_path = database.get_database_path(config.CONFIG_FILE_PATH)
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


