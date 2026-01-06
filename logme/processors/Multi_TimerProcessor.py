from importlib import resources as impresources
import logging, typer, pandas as pd
import json
import logme.utils.Utils as u
from logme.utils import ProcessingUtils
# import logme.storage 
from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
from logme.utils.Utils import get_database_path
#from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)

class Multi_TimerProcessor:
    """
    Class to process Multi Timer data
    """

    def __init__(self, files: list[str]) -> None:
        self.files = files
        self.src = "Multi_Timer"
        self.conf = u.get_source_conf(self.src, f'{self.src}')
        self.conf_raw_to_l1 = u.get_source_conf(self.src, f'{self.src}_raw_to_l1')
        self.conf_l1_to_l2 = u.get_source_conf(self.src, f'{self.src}_l1_to_l2')
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Starting Multi_TimerProcessor')
        if config.CONFIG_FILE_PATH.exists():
            db_path = get_database_path(config.CONFIG_FILE_PATH)
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

    def landing_to_raw(self) -> list[pd.DataFrame]:
        self.check_data_quality()
        if ProcessingUtils._table_exists(f'{self.src}_raw') != True:
            self.logger.info(f'Creating raw table {self.src}_raw')
            query = ProcessingUtils._query_from_list_of_fields(self.src, "raw", self.conf["fields"], self.conf["fields_format"])
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
    
    def raw_to_l1(self, dfs: list[pd.DataFrame]) -> list[pd.DataFrame]:
        dfs_casted = []
        if ProcessingUtils._table_exists(f'{self.src}_l1') != True:
            self.logger.info(f'Creating l1 table {self.src}_l1')
            ddl_file = impresources.files(logme.storage) / f'{self.src}_l1.sql'
            query = open(ddl_file, "rt").read().format(name=self.src)
            if ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_l1")
        for df in dfs:
            print(df.info())
            # print(df[cols_raw[5]])
            df_casted = ProcessingUtils._raw_to_l1_types(df,self.conf, self.conf_raw_to_l1)
            self._db_handler.df_to_db(df_casted,f'{self.src}_l1')
            dfs_casted.append(df_casted)
        return dfs_casted
    
    def l1_to_l2(self, dfs: list[pd.DataFrame]) -> list[pd.DataFrame]:
        dfs_out = []
        if ProcessingUtils._table_exists(f'{self.src}_l2') != True:
            self.logger.info(f'Creating l2 table {self.src}_l2')
            ddl_file = impresources.files(logme.storage) / f'{self.src}_l2.sql'
            query = open(ddl_file, "rt").read().format(name=self.src)
            if ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_l1")
        for df in dfs:
            names = set(df['name'].tolist())
            actions = set(df['action'].tolist())
            print(names)
            print(actions)
            for name in names:
                df1 = df[(df['name']==name) & (df['action'].str.contains('Start'))][['name','ts','duration_sec','process_ts']]
                df1['in_group'] = 'Salud'
                df1['ts_to'] = df1['ts'] + df1['duration_sec']
                df1['src'] = self.src
                df1['ts_added'] = df1['process_ts']
                df1['comment'] = ''
                df1 = ProcessingUtils._add_hash(df1)
                df1 = df1.rename(columns={"ts": "ts_from", "name":"activity"})
                df1 = df1[["in_group",'activity','comment','duration_sec','ts_from','ts_to','src','ts_added', 'hash']]
                self._db_handler.df_to_db(df1,f'{self.src}_l2')
            # TODO:
            # Cambia el nombre si se cambia el idioma del telefono?!
            dfs_out.append(df1)
        return dfs_out