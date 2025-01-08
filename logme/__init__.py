"""Top-level package for logme."""

from os import path, environ, mkdir
import sys
import collections
from pathlib import Path
import configparser
from dotenv import load_dotenv
import typer
import logging
from datetime import datetime
if sys.version_info.major == 3 and sys.version_info.minor >= 10:
    from collections.abc import MutableMapping
    setattr(collections, "MutableMapping", collections.abc.MutableMapping)
else:
    from collections import MutableMapping

__app_name__ = "logme"
__version__ = "0.1.0"

now = datetime.now()  # current date and time
date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
logger = logging.getLogger(__app_name__)
if not path.exists('logs'):
    mkdir('logs')
logging.basicConfig(format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                    filename=f'logs/{date_time}.log', 
                    encoding='utf-8', 
                    level=logging.INFO)
CONFIG_DIR_PATH = Path(typer.get_app_dir(__app_name__))
logger.info(f"CONFIG_DIR_PATH: {CONFIG_DIR_PATH}")
CONFIG_FILE_PATH = CONFIG_DIR_PATH / "config.ini"
logger.info(f"CONFIG_FILE_PATH: {CONFIG_FILE_PATH}")

(
    SUCCESS,
    DIR_ERROR,
    FILE_ERROR,
    DB_READ_ERROR,
    DB_WRITE_ERROR,
    JSON_ERROR,
    ID_ERROR,
) = range(7)

ERRORS = {
    DIR_ERROR: "config directory error",
    FILE_ERROR: "config file error",
    DB_READ_ERROR: "database read error",
    DB_WRITE_ERROR: "database write error",
    ID_ERROR: "to-do id error",
}

SCOPES = ['https://www.googleapis.com/auth/drive']

load_dotenv('.env')

creds_dict = {
    "type": environ.get('type'),
    "project_id": environ.get('project_id'),
    "private_key_id": environ.get('private_key_id'),
    "private_key": environ.get('private_key'),
    "client_email": environ.get('client_email'),
    "client_id": environ.get('client_id'),
    "auth_uri": environ.get('auth_uri'),
    "token_uri": environ.get('token_uri'),
    "auth_provider_x509_cert_url": environ.get('auth_provider_x509_cert_url'),
    "client_x509_cert_url": environ.get('client_x509_cert_url')
}

config_parser = configparser.ConfigParser()
try:
    config_parser.read(CONFIG_FILE_PATH)
    sourcesList = config_parser.get("Sources", "src").split(",")
    duolingo_languages = config_parser.get("duolingo", "languages").split(",")
    duolingo_end_points = config_parser.get("duolingo", "end_points").split(",")
    instagram_tmpdir = config_parser.get("instagram", "tmpdir")
    instagram_external_hdd = config_parser.get("instagram","external_hdd")
    instagram_cookiefile = config_parser.get("instagram", "cookiefile")
    instagram_sessionfile = config_parser.get("instagram","sessionfile")
except:
    FILE_ERROR