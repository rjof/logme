import json
import os.path
from sqlalchemy import (create_engine, sql)
from logme import (config, ingestion, SUCCESS,
                   logme, JSON_ERROR, DB_READ_ERROR, now, date_time)
from logme.storage.database import (DatabaseHandler, SQLiteResponse, DBResponse)
from os import makedirs
import typer
from pathlib import Path
import pandas as pd
import re
import logging
import logme.utils.Utils

class KoreaderClippingIngest:
    """
    Class to process the highlighted texts in Koreader
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
        Moves the KOReaderClipping.txt file from the koreader->src_file
        loacation in the config file to LocalPaths->storage/KoreaderStatistics/
        :return:
        """
#        dst_path = Path(self.dst) / self.src
        dst_path = Path(self.dst) / self.src / f"{date_time}"
        if not dst_path.exists():
            makedirs(dst_path)
        # check if file in koreader->connection is newer than
        files = [i.strip(" ") for i in self.conf['src_file'].split(",")]
        for f in files:
            Utils.move_file_in_local_system(Path(f), dst_path)

    def pre_process(self) -> pd.DataFrame:
        """
        Prepare the dataframe with the texts
        :return: pandas dataframe of texts
        """
        self.move_from_landing()
        
        # dst_path = Path(self.dst) / self.src
        dst_path = Path(self.dst) / self.src / f"{date_time}"
        patternBeginNote = "(^[\\t\\s]+-- Página: [0-9]*, añadida a (.*)\n|^[\\t\\s]+—Page : [0-9]*, ajouté (.*)\n)"
        patternEndNote = "-=-=-=-=-=-"
        patternNote = "Página [0-9]* "
        data = [["a","b","c"]]
        for filePath in os.listdir(dst_path):
            file = open(Path(self.dst) / self.src / filePath)
            bookTitle = ""
            inNote = 0
            endNote = 0
            noteDate = ""
            note = ""
            i = 0
            line = file.readline()
            endCycle = 0
            while endCycle == 0:
                endNote = re.findall(patternEndNote, line)
                if endNote:
                    line = file.readline()
                beginNote = re.findall(patternBeginNote, line)
                endNote = re.findall(patternEndNote, line)

                if beginNote:
                    noteDate = beginNote[0]
                    note = file.readline()
                    data.append([bookTitle, note, noteDate])
                    line = file.readline()
                beginNote = re.findall(patternBeginNote, line)
                endNote = re.findall(patternEndNote, line)

                if not beginNote and not endNote:
                    self.logger.info(f"bookTile should be: {line}")
                    bookTitle = line.replace(u"\u3000", "")
                    line = file.readline()
                # print(f"{i}: {line}")
                print(f"  bookTitle: {bookTitle}")
                # print(f"  note:      {note}")
                # print(f"  noteDate:  {noteDate}")
                # print(f"  line:      {line}")
                i = i + 1
                if i == 30:
                    endCycle = 1
        file.close()
        print("======= data:")
        print(data)