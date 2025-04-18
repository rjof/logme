from importlib import resources as impresources
import logme.storage 
from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
import logme.storage.database as db
from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)
import logging, typer, pandas as pd
from logme.utils import ProcessingUtils

class Multi_TimerProcessor:
    """
    Class to process Multi Timer data
    """

    def __init__(self, files: list[str], conf: dict) -> None:
        self.files = files
        self.conf = conf
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
    
    def raw_to_l1(self, dfs: list[pd.DataFrame]) -> int:
        for df in dfs:
            print(df)
            print(df.info())
            if ProcessingUtils._table_exists(f'{self.src}_l1') != True:
                self.logger.info(f'Creating l1 table {self.src}_l1')
                ddl_file = impresources.files(logme.storage) / f'{self.src}_l1.sql'
                query = open(ddl_file, "rt").read().format(name=self.src)
                if ProcessingUtils._create_table(query) != SUCCESS:
                    raise typer.Exit(f"Error creating {self.src}_l1")
            # Basic processes
            # 1. ts:
            #   From "Nov 10, 2023 12:46:26 AM" (conf['date_format']=%%b %%-d, %%Y %%-H:%%M:%%S)
            #   To unixtimestamp
            # 2. elapsed_sec:
            #   From [+]%%M:%%S
            #   To integer seconds... what [+] means?
            # 3. duration
            #   From %%M:%%S
            #   To integer seconds
            # 4. Add hash
            # 5. process_ts fill with now_ts

        return DB_READ_ERROR
    