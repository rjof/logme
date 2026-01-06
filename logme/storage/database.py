"""This module provides the logme database functionality."""

import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple
from os import path
import pandas as pd
from sqlalchemy import (
    inspect,
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    sql,
    text
)
from logme.ddl import InstagramRow
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import IntegrityError
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker  # , declarative_base
from logme import DB_READ_ERROR, DB_WRITE_ERROR, JSON_ERROR, SUCCESS

DEFAULT_DB_FILE_PATH = Path.home().joinpath("." + Path.home().stem + "_logme.db")


class DBResponse(NamedTuple):
    todo_list: List[Dict[str, Any]]
    error: int


class SQLiteResponse(NamedTuple):
    logme_df: pd.DataFrame
    error: int


class DatabaseHandler:
    # @todo: For sqlite. This is the original
    #        code for a json of to-do
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def init_database(self) -> int:
        """Create the logme database."""
        if path.isfile(self._db_path):
            return SUCCESS
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            # sqlite_connection = engine.connect()
            meta = MetaData()
            logme = Table(
                "logme",
                meta,
                Column("in_group", String),
                Column("activity", String),
                Column("comment", String),
                Column("duration_sec", Integer),
                Column("ts_from", Integer),
                Column("ts_to", Integer),
                Column("src", String),
                Column("ts_added", Integer),
                Column("hash", String, primary_key=True),
            )
            meta.create_all(engine)
            return SUCCESS
        except OSError:
            return DB_WRITE_ERROR

    def _list_columns(self, table: str) -> list:
        """
        List the columns of a table
        """
        print(f"table: {table}")
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            inspection = inspect(engine)
            columns_table = inspection.get_columns(table)
            return [c["name"] for c in columns_table]
        except OSError:  # Catch file IO problems
            return [DB_READ_ERROR]

    def _list_tables(self) -> SQLiteResponse:
        """
        List all the tables in the database

        Usage example:

            df, err = self._db_handler._list_tables()
            if err != SUCCESS:
                msg = f"The database was not found or readable."
                raise Exception(msg)
            self.logger.info(f"df: {df}")
        """
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            with engine.connect() as sqlite_connection:
                try:
                    sql_query = sql.text(
                        """SELECT name FROM sqlite_master WHERE type='table'"""
                    )
                    list_logme = sqlite_connection.execute(sql_query).fetchall()
                    return SQLiteResponse(
                        pd.DataFrame(list_logme, columns=["name"]), SUCCESS
                    )
                except OSError:  # Catch file IO problems
                    return DBResponse([], DB_READ_ERROR)
        except OSError:  # Catch file IO problems
            return SQLiteResponse(pd.DataFrame(), DB_READ_ERROR)

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
            with engine.connect() as sqlite_connection:
                try:
                    sql_query = sql.text("select * from logme")
                    list_logme = sqlite_connection.execute(sql_query).fetchall()
                    return SQLiteResponse(
                        pd.DataFrame(
                            list_logme,
                            columns=[
                                "hash",
                                "in_group",
                                "activity",
                                "comment",
                                "duration_sec",
                                "ts_from",
                                "ts_to",
                                "src",
                                "ts_added",
                            ],
                        ),
                        SUCCESS,
                    )
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
                    df.to_sql(
                        sqlite_table, conn.connection, index=False, if_exists="append"
                    )
                except OSError:
                    return DB_READ_ERROR
        except OSError:  # Catch file IO problems
            return DB_READ_ERROR

    def df_to_db(self, *, df: pd.DataFrame, table_name: str) -> int:
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            with engine.connect() as conn:
                try:

                    df.to_sql(
                        table_name, conn.connection, index=False, if_exists="append"
                    )
                    return SUCCESS
                except IntegrityError as e:
                    # session.rollback() # Rollback the transaction on error
                    print(f"Skipping '{df['hash']}' due to IntegrityError: {e.orig}")
                except OSError:
                    return DB_WRITE_ERROR
        except OSError:  # Catch file IO problems
            return DB_WRITE_ERROR
        finally:
            pass

    

    def raw_instagram_row_to_db(self, row: InstagramRow):
        sqlite_db = f"sqlite:///{self._db_path}"
        engine = create_engine(sqlite_db, echo=True)
        Base = declarative_base()
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            session.add(row)
            session.commit()
            return SUCCESS
        except IntegrityError as e:
            session.rollback()
            print(f"Integrity error: {e.orig}")
        finally:
            return SUCCESS
        # except OSError:
        #     return DB_WRITE_ERROR


    def fields_in_table(self, table_name: str) -> List[str]:
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            raw_conn = engine.raw_connection()
            cursor = raw_conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = sorted(set({col[1] for col in cursor.fetchall()}))
            return existing_columns
        except OSError:
            return DB_READ_ERROR
        except OSError:  # Catch file IO problems
            return DB_READ_ERROR


    def alter_table(self, table_name, new_col):
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            sqlite_table = "logme"
            engine = create_engine(sqlite_db, echo=True)

            with engine.connect() as conn:
                try:
                    alter_sql = text(f"ALTER TABLE \"{table_name}\" ADD COLUMN \"{new_col}\" String NULL")
                    conn.execute(alter_sql)
                except OSError:
                    return DB_READ_ERROR
        except OSError:  # Catch file IO problems
            return DB_READ_ERROR


    def row_to_raw_instagram(self, table_name, placeholders, quoted_columns, values):
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            raw_conn = engine.raw_connection()
            cursor = raw_conn.cursor()
            insert_sql = f"INSERT INTO \"{table_name}\" ({quoted_columns}) VALUES ({placeholders})"

            try:
                cursor.execute(insert_sql, values)
            except OSError:  # Catch file IO problems
                return DB_READ_ERROR
            raw_conn.commit()
            print(f"Row inserted in {table_name}")
        except OSError:  # Catch file IO problems
            return DB_READ_ERROR
