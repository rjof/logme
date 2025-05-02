"""This module provides the logme config functionality."""

import configparser
from pathlib import Path
from os import makedirs, path

import typer

from logme import DB_WRITE_ERROR, DIR_ERROR, FILE_ERROR, SUCCESS, __app_name__
from .storage.database import init_database

CONFIG_DIR_PATH = Path(typer.get_app_dir(__app_name__))
CONFIG_FILE_PATH = CONFIG_DIR_PATH / "config.ini"
config_parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config_parser.optionxform=str


def init_app(db_path: str) -> int:
    """Initialize the application."""
    database_code = init_database(db_path)
    if database_code != SUCCESS:
        return database_code
    # zones_code = _create_zone_paths
    # if zones_code != SUCCESS:
    #     return zones_code
    return SUCCESS


def _init_config_file() -> int:
    try:
        CONFIG_DIR_PATH.mkdir(exist_ok=False)
    except OSError:
        return DIR_ERROR
    try:
        CONFIG_FILE_PATH.touch(exist_ok=True)
    except OSError:
        return FILE_ERROR
    return SUCCESS


def _create_database(db_path: str) -> int:
    config_parser["General"] = {"database": db_path}
    # # @todo
    # # create the variable
    # config_parser["LocalPaths"] = {"storage": "/home/rjof/logme_data"}
    # config_parser["LocalPaths"] = {"logs_path": "/home/rjof/logme_data/logs"}
    # config_parser["LocalPaths"] = {"landing_path": "/home/rjof/logme_data/landing"}
    # config_parser["LocalPaths"] = {"history_path": "/home/rjof/logme_data/history"}
    try:
        with CONFIG_FILE_PATH.open("w") as file:
            config_parser.write(file)
    except OSError:
        return DB_WRITE_ERROR
    return SUCCESS
 
# def _create_zone_paths() -> int:
#     try:
#         makedirs(Path(configparser["LocalPaths"]["storage"]))
#         makedirs(Path(configparser["LocalPaths"]["logs_path"]))
#         makedirs(Path(configparser["LocalPaths"]["landing_path"]))
#         makedirs(Path(configparser["LocalPaths"]["history_path"]))
#     except OSError:
#         return DIR_ERROR
#     return SUCCESS