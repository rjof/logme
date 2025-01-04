"""This module provides the logme database functionality."""

import configparser
import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

import pandas as pd
from sqlalchemy import (create_engine, MetaData, Table,Column, Integer, String, sql)
from logme import (DB_READ_ERROR, DB_WRITE_ERROR, JSON_ERROR,SUCCESS)

DEFAULT_DB_FILE_PATH = Path.home().joinpath(
    "." + Path.home().stem + "_logme.db"
)


def get_database_path(config_file: Path) -> Path:
    """Return the local storage of collected files."""
    config_parser = configparser.ConfigParser()
    config_parser.read(config_file)
    return Path(config_parser["General"]["database"])


def init_database(db_path: Path) -> int:
    """Create the logme database."""
    try:
        sqlite_db = f"sqlite:///{db_path}"
        engine = create_engine(sqlite_db, echo=True)
        # sqlite_connection = engine.connect()
        meta = MetaData()
        logme = Table('logme', meta,
                      Column('hash',         String, primary_key = True),
                      Column('in_group',     String),
                      Column('activity',     String),
                      Column('comment',      String),
                      Column('duration_sec', Integer),
                      Column('ts_from',      Integer),
                      Column('ts_to',        Integer),
                      )
        meta.create_all(engine)
        #db_path.write_text("[]")  # Empty to-do list
        return SUCCESS
    except OSError:
        return DB_WRITE_ERROR


class DBResponse(NamedTuple):
    todo_list: List[Dict[str, Any]]
    error: int


class SQLiteResponse(NamedTuple):
    logme_merged: pd.DataFrame
    error: int

class DatabaseHandler:
    # @todo: For sqlite. This is the original
    #        code for a json of to-do
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def read_logme(self) -> DBResponse:
        try:
            with self._db_path.open("r") as db:
                try:
                    return DBResponse(json.load(db), SUCCESS)
                except json.JSONDecodeError:  # Catch wrong JSON format
                    return DBResponse([], JSON_ERROR)
        except OSError:  # Catch file IO problems
            return DBResponse([], DB_READ_ERROR)

    def write_todo(self, logme_list: List[Dict[str, Any]]) -> DBResponse:
        try:
            with self._db_path.open("w") as db:
                json.dump(logme_list, db, indent=4)
            return DBResponse(logme_list, SUCCESS)
        except OSError:  # Catch file IO problems
            return DBResponse(logme_list, DB_WRITE_ERROR)

    def load_logme(self) -> SQLiteResponse:
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            with engine.connect() as  sqlite_connection:
                try:
                    sql_query = sql.text('select * from logme')
                    list_logme = sqlite_connection.execute(
                        sql_query).fetchall()
                    return SQLiteResponse(
                        pd.DataFrame(
                            list_logme,
                        columns=['hash', 'in_group','activity',
                                 'comment','duration_sec',
                                 'ts_from','ts_to']),
                        SUCCESS)
                except OSError:  # Catch file IO problems
                    return DBResponse([], DB_READ_ERROR)
        except OSError:  # Catch file IO problems
            return SQLiteResponse(pd.DataFrame(), DB_READ_ERROR)

    def write_logme(self, df: pd.DataFrame) -> int:
        # @todo Create a backup before writing
        # drop table logmeBK if exists;
        # create table logmeBK as select * from logme;

        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            sqlite_table = "logme"
            engine = create_engine(sqlite_db, echo=True)
            with engine.connect() as conn:
                try:
                    df.to_sql(sqlite_table,conn.connection ,index=False,if_exists='append')
                except OSError:
                    return DB_READ_ERROR
        except OSError:  # Catch file IO problems
            return DB_READ_ERROR
