import json
import os.path
from sqlalchemy import (create_engine, sql)
from logme import (config, database, sources, SUCCESS,
                   logme, JSON_ERROR, DB_READ_ERROR)
from logme.database import (DatabaseHandler, SQLiteResponse,
                            DBResponse)
from os import makedirs
import typer
from pathlib import Path
import pandas as pd
import re

class KoreaderClipping:
    """
    Class to process the highlighted texts in Koreader
    """

    def __init__(self, src: Path, dst: Path) -> None:
        self.src = src
        self.dst = dst
        self.conf = logme.get_source_conf(self.src)
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
        Moves the KOReaderClipping.txt file from the koreader->src_file
        loacation in the config file to LocalPaths->storage/KoreaderStatistics/
        :return:
        """
        dst_path = Path(self.dst) / self.src
        if not dst_path.exists():
            makedirs(dst_path)
        # check if file in koreader->connection is newer than
        files = [i.strip(" ") for i in self.conf['src_file'].split(",")]
        for f in files:
            logme.move_file_in_local_system(Path(f), dst_path)

    def pre_process(self) -> pd.DataFrame:
        """
        Prepare the dataframe with the texts
        :return: pandas dataframe of texts
        """
        self.move_from_landing()
        
        dst_path = Path(self.dst) / self.src
        patternBeginNote = "^[\\t\\s]+-- Página: [0-9]*, añadida a (.*)\n"
        patternNote = "Página [0-9]* "
        for filePath in os.listdir(dst_path):
            file = open(Path(self.dst) / self.src / filePath)
            bookTitle = ""
            inNote = 0
            endNote = 0
            i = 0
            line = ""
            while endNote == 0:
                if line == "-=-=-=-=-=-\n":
                    bookTitle = ""
                    line = file.readline()
                if bookTitle == "":
                    bookTitle = line
                    # line = file.readline()
                res = re.findall(patternBeginNote, line)
                if res:
                    print(res)
                    inNote = 1
                    # line = file.readline()
                print(f"${i}: ${line}")
                print(f"  bookTitle: ${bookTitle}")
                print(f"  res: ${res}")
                line = file.readline()
                i = i + 1
                if i == 10:
                    endNote = 1
        file.close()
