from logme import SUCCESS, DB_READ_ERROR, DB_WRITE_ERROR, config
import logme.storage.database as db
from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)
import logging, typer

class Multi_TimerProcessor:
    """
    Class to process Multi Timer data
    """

    def __init__(self, files: list[str], conf: dict) -> None:
        self.files = files
        self.conf = conf
        self.logger = logging.getLogger(self.__class__.__name__)
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
        if self._raw_table_exists() != SUCCESS:
            raise typer.Exit("Missing raw table")

    def check_data_quality(self) -> int:
        return SUCCESS
    
    def _are_headers_correct(self) -> int:
        return SUCCESS
    
    def _are_field_types_correct(self) -> int:
        return SUCCESS
    
    def _raw_table_exists(self) -> int:
        return DB_READ_ERROR
    
    def _insert_into_multi_timer_raw(self) -> SQLiteResponse:
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
