"""Top-level package for logme."""

import sys
import collections 
if sys.version_info.major == 3 and sys.version_info.minor >= 10:
    from collections.abc import MutableMapping
    setattr(collections, "MutableMapping", collections.abc.MutableMapping)
else:
    from collections import MutableMapping
from dotenv import load_dotenv
from os import path, environ
import configparser
from pathlib import Path
import typer

__app_name__ = "logme"
__version__ = "0.1.0"


CONFIG_DIR_PATH = Path(typer.get_app_dir(__app_name__))
CONFIG_FILE_PATH = CONFIG_DIR_PATH / "config.ini"

config_parser = configparser.ConfigParser()
config_parser.read(CONFIG_FILE_PATH)
sources = config_parser.get("Sources", "src").split(",")


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
    "type"                        : environ.get('type'),
    "project_id"                  : environ.get('project_id'),
    "private_key_id"              : environ.get('private_key_id'),
    "private_key"                 : environ.get('private_key'),
    "client_email"                : environ.get('client_email'),
    "client_id"                   : environ.get('client_id'),
    "auth_uri"                    : environ.get('auth_uri'),
    "token_uri"                   : environ.get('token_uri'),
    "auth_provider_x509_cert_url" : environ.get('auth_provider_x509_cert_url'),
    "client_x509_cert_url"        : environ.get('client_x509_cert_url')
}
