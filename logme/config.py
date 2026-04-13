"""This module provides the logme config functionality."""

import configparser
from pathlib import Path
from os import makedirs, path

import typer

from logme import DB_WRITE_ERROR, DIR_ERROR, FILE_ERROR, SUCCESS, __app_name__

CONFIG_DIR_PATH = Path(typer.get_app_dir(__app_name__))
CONFIG_FILE_PATH = CONFIG_DIR_PATH / "config.ini"
config_parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
config_parser.optionxform=str


def init_app(db_path: str) -> int:
    """Initialize the application."""
    config_code = _init_config_file()
    if config_code != SUCCESS:
        return config_code
    database_code = _create_database(db_path)
    if database_code != SUCCESS:
        return database_code
    # zones_code = _create_zone_paths
    # if zones_code != SUCCESS:
    #     return zones_code
    return SUCCESS


def _init_config_file() -> int:
    try:
        CONFIG_DIR_PATH.mkdir(parents=True, exist_ok=True)
    except OSError:
        return DIR_ERROR
    return SUCCESS


def _create_database(db_path: str) -> int:
    base_data_path = Path.home() / "logme_data"
    config_parser["General"] = {
        "database": db_path,
        "base_path": str(base_data_path)
    }
    config_parser["LocalPaths"] = {
        "storage": str(base_data_path),
        "logs_path": str(base_data_path / "logs"),
        "landing_path": str(base_data_path / "landing"),
        "history_path": str(base_data_path / "history"),
    }
    config_parser["Sources"] = {
        "src": "aTimeLogger,duolingo,koreaderStatistics,koreaderClipping,instagram,Multi_Timer"
    }
    try:
        with CONFIG_FILE_PATH.open("w") as file:
            config_parser.write(file)
    except OSError:
        return DB_WRITE_ERROR
    return SUCCESS
 

