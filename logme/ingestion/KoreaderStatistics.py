import json
import os.path
from sqlalchemy import (create_engine, sql)
from logme import (config, SUCCESS, now, date_time,
                   logme, JSON_ERROR, DB_READ_ERROR)
from logme.storage.database import (DatabaseHandler, SQLiteResponse,
                            DBResponse)
from os import makedirs
import typer
from pathlib import Path
import pandas as pd
import logging
import time
import numpy as np
import logme.utils.Utils


class KoreaderStatistics:
    """
    Class to process sqlite files from Koreader
    """

    def __init__(self, src: Path, dst: Path) -> None:
        self.src = src
        self.dst = dst
        self.conf = logme.get_source_conf(self.src)
        self.logger = logging.getLogger(self.__class__.__name__)
        if config.CONFIG_FILE_PATH.exists():
            db_path = database.get_database_path(config.CONFIG_FILE_PATH)
        else:
            typer.secho(
                'Config file not found. Please, run "logme init"',
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        if not db_path.exists():
            typer.secho(
                'Database not found. Please, run "logme init"',
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)
        self._db_handler = DatabaseHandler(db_path)

    def move_from_landing(self):
        """
        Moves the files from the koreader->src_file
        loacation in the config file to LocalPaths->storage/KoreaderStatistics/
        :return:
        """
        # check if file in koreader->connection is newer than
        # dst_path = Path(self.dst) / self.src
        dst_path = Path(self.dst) / self.src / f"{date_time}"
        if not dst_path.exists():
            makedirs(dst_path)
        files = [i.strip(" ") for i in self.conf['src_file'].split(",")]
        for f in files:
            Utils.move_file_in_local_system(Path(f), dst_path)

    def process(self) -> pd.DataFrame:
        """
        Prepare the dataframe to be saved in the logme database
        :return: pandas dataframe of new reading activities
        """
        # Run this query and put it in a pandas dataframe
        # SELECT book.title AS activity,
        # page_stat.page AS comment,
        # page_stat.duration AS duration_sec,
        # page_stat.start_time AS ts_from,
        # (page_stat.start_time + page_stat.duration) AS ts_to
        # FROM page_stat
        # INNER JOIN book ON book.id = page_stat.id_book ORDER BY start_time;
        self.move_from_landing()
        logme_df, err = self._db_handler.load_logme()
        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        self.logger.info(f"logme_df: {logme_df.shape}")
        db_file_statistics = self.dst / self.src / os.path.basename(self.conf['src_file'])
        self.logger.info(f"db_file_statistics shape: {db_file_statistics}")
        _db_statistics = KoreaderDatabaseHandler(db_file_statistics)
        # The comment field is the page number of the book
        statistics_df, err = _db_statistics.load_statistics()
        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        # Change type int64 to object
        statistics_df['comment'] = statistics_df['comment'].astype(str)
        statistics_df['hash'] = pd.util.hash_pandas_object(statistics_df)
        # Change type from unit64 to object
        statistics_df['hash'] = statistics_df['hash'].astype(str)
        statistics_df['in_group'] = str("Leo")
        statistics_df = \
            statistics_df[['hash','in_group','activity',
                           'comment','duration_sec',
                           'ts_from','ts_to']]

        # self.logger.info(statistics_df.info())
        # self.logger.info(logme_df.info())

        merged = statistics_df.merge(
            logme_df.drop_duplicates(),
            on=['in_group',
                'activity', 'comment',
                'duration_sec', 'ts_from', 'ts_to'],
            how='left', indicator=True)
        # self.logger.info(merged.head(10))
        # self.logger.info(merged.info())
        merged.rename(columns={'hash_x': 'hash'}, inplace=True)

        already_saved = merged[merged['_merge']=='both']
        to_save = merged[merged['_merge']!='both']
        to_save = to_save[statistics_df.columns]
        num_rows = len(to_save.index)
        ts_added = int(time.mktime(now.timetuple()))
        date_col = np.repeat(ts_added, num_rows)
        src_col = np.repeat(self.src, num_rows)
        to_save['src'] = src_col
        to_save['ts_added'] = date_col
        self.logger.info(f"loaded:         {statistics_df.shape}")
        self.logger.info(f"merged:         {merged.shape}")
        self.logger.info(f"already_saved:  {already_saved.shape}")
        self.logger.info(f"To be inserted: {to_save.shape}")
        self.logger.info(f"Some rows: {to_save}")

        return self._db_handler.write_logme(to_save)

class KoreaderDatabaseHandler:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"self db path: {self._db_path}")

    def read_statistics(self) -> DBResponse:
        try:
            with self._db_path.open("r") as db:
                try:
                    return DBResponse(json.load(db), SUCCESS)
                except json.JSONDecodeError:  # Catch wrong JSON format
                    return DBResponse([], JSON_ERROR)
        except OSError:  # Catch file IO problems
            return DBResponse([], DB_READ_ERROR)

    def load_statistics(self) -> SQLiteResponse:
        try:
            sqlite_db = f"sqlite:///{self._db_path}"
            engine = create_engine(sqlite_db, echo=True)
            with engine.connect() as  sqlite_connection:
                try:
                    sql_query = sql.text(
                        """
                        SELECT book.title AS activity,
                        page_stat.page AS comment,
                        page_stat.duration AS duration_sec,
                        page_stat.start_time AS ts_from,
                        (page_stat.start_time + page_stat.duration) AS ts_to
                        FROM page_stat
                        INNER JOIN book ON book.id = page_stat.id_book 
                        ORDER BY start_time
                        """)
                    list_logme = sqlite_connection.execute(
                        sql_query).fetchall()
                    # @todo Put columnames in config?
                    return SQLiteResponse(pd.DataFrame(
                        list_logme,
                        columns=['activity', 'comment',
                                 'duration_sec', 'ts_from',
                                 'ts_to']),
                        SUCCESS)
                except OSError:  # Catch file IO problems
                    return DBResponse([], DB_READ_ERROR)
        except OSError:  # Catch file IO problems
            return SQLiteResponse(pd.DataFrame(), DB_READ_ERROR)
