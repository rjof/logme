from importlib import resources as impresources
import logme.storage 
from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
import logme.storage.database as db
from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)
import logging, typer, pandas as pd
from logme.utils import ProcessingUtils
import json

class Multi_TimerProcessor:
    """
    Class to process Multi Timer data
    """

    def __init__(self, files: list[str], conf: dict, confTransformations: dict) -> None:
        self.files = files
        self.conf = conf
        self.confTransformations = confTransformations
        self.src = "Multi_Timer"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Starting Multi_TimerProcessor')
        if config.CONFIG_FILE_PATH.exists():
            db_path = db.get_database_path(config.CONFIG_FILE_PATH)
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
        self._db_handler = db.DatabaseHandler(db_path)

    def landing_to_raw(self) -> pd.DataFrame:
        self.check_data_quality()
        if ProcessingUtils._table_exists(f'{self.src}_raw') != True:
            self.logger.info(f'Creating raw table {self.src}_raw')
            query = ProcessingUtils._query_from_list_of_fields(self.src, "raw", self.conf["fields"])
            if ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_raw")
        dfs = []
        for file in self.files:
            dfs.append(ProcessingUtils._ingest_file_to_db(file, f'{self.src}_raw', self.conf))
        return dfs

    def check_data_quality(self) -> int:
        # If conf has header, check the names
        if self.conf['header']:
            if ProcessingUtils._are_headers_correct(self.files, self.conf):
                self.logger.info(f'Headers are correct')
            else:
                self.logger.info("Wrong headers")
        return SUCCESS
    
    def raw_to_l1(self, dfs: list[pd.DataFrame]) -> pd.DataFrame:
        dfs_casted = []
        for df in dfs:
            print(df.info())
            # print(df[cols_raw[5]])
            if ProcessingUtils._table_exists(f'{self.src}_l1') != True:
                self.logger.info(f'Creating l1 table {self.src}_l1')
                ddl_file = impresources.files(logme.storage) / f'{self.src}_l1.sql'
                query = open(ddl_file, "rt").read().format(name=self.src)
                if ProcessingUtils._create_table(query) != SUCCESS:
                    raise typer.Exit(f"Error creating {self.src}_l1")
            df_casted = ProcessingUtils._raw_to_l1_types(df,self.conf, self.confTransformations)
            dfs_casted.append(self._db_handler.df_to_db(df_casted,f'{self.src}_l1'))
        return dfs_casted
    