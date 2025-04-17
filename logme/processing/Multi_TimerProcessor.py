from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
import logme.storage.database as db
from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)
import logging, typer
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
        self._landing_to_raw()

    def _landing_to_raw(self) -> int:
        self.check_data_quality()
        if ProcessingUtils._raw_table_exists(self.src) != True:
            self.logger.info(f'Creating raw table {self.src}_raw')
            query = ProcessingUtils._query_from_list_of_fields(self.src, "raw", self.conf["fields"])
            if ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_raw")
        for file in self.files:
            print(f'file: {file}')
            if ProcessingUtils._ingest_file_to_db(file, f'{self.src}_raw', self.conf) != SUCCESS:
                self.logger.info(f'Error putting {file} to {self.src}_raw')
            else:
                self.logger.info(f'Loaded {file} to {self.src}_raw')

    def check_data_quality(self) -> int:
        # If conf has header, check the names
        if self.conf['header']:
            if ProcessingUtils._are_headers_correct(self.files, self.conf):
                self.logger.info(f'Headers are correct')
            else:
                self.logger.info("Wrong headers")
    
        return SUCCESS
    