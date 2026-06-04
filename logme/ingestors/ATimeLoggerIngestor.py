from dotenv import load_dotenv
from json import load, dump
from logme import config, SUCCESS, now, date_time
from logme.utils.Utils import get_database_path
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
import logme.utils.Utils as u
from logme.storage.database import DatabaseHandler


class ATimeLoggerIngestor:
    """Class to call the aTimeLogger api"""

    def __init__(self, src: str, dst: Path, conf) -> None:
        self.src = src
        self.dst = dst
        self.conf = conf
        self.logger = logging.getLogger(self.__class__.__name__)

        if config.CONFIG_FILE_PATH.exists():
            db_path = get_database_path(config.CONFIG_FILE_PATH)
        else:
            typer.secho('Config file not found. Please, run "logme init"', fg=typer.colors.RED)
            raise typer.Exit(1)
            
        if not db_path.exists():
            typer.secho('Database not found. Please, run "logme init"', fg=typer.colors.RED)
            raise typer.Exit(1)
        self._db_handler = DatabaseHandler(db_path)

    def download(self) -> int:
        error = 0
        if not self.dst.exists():
            makedirs(self.dst)
        load_dotenv(".env")
        user = environ.get("aTimeLogger_user")
        password = environ.get("aTimeLogger_pass")
        
        days_to_retrieve = self.conf.get("days_to_retrieve_api", 7)
        from_secs = int(time.time()) - int(days_to_retrieve * 24 * 60 * 60)
        
        # The logic of limit, which is how many activities to download, is to assume
        # that the maximum to download is the number of seconds in the interval
        # divided by 5 minutes (300 seconds)
        limit = int((int(time.time()) - from_secs) / 300)
        if limit < 200: limit = 200 # Minimum limit

        urls = [
            "https://app.atimelogger.com/api/v2/activities?limit=200",
            f"https://app.atimelogger.com/api/v2/intervals?limit={limit}&from={from_secs}",
        ]
        
        for url in urls:
            self.logger.info(f"Downloading from {url}")
            resp = requests.get(url, auth=HTTPBasicAuth(user, password))
            if not resp.status_code == 200:
                error = 1
                self.logger.error(f"Failed to download from {url}: {resp.status_code}")
                raise Exception(
                    f"The aTimeLogger api seems to be down... or your request? Status: {resp.status_code}"
                )
            
            self.logger.info(f"{url}: {resp.status_code}")
            dst_file = Path(self.dst) / f"{urlparse(url).path.split('/')[-1]}.json"
            self.logger.info(f"dst file: {dst_file}")
            with open(dst_file, "w") as f:
                dump(resp.json(), f)
                
        return error
