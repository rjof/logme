import json

from dotenv import load_dotenv
from json import load, dump
from logme import (config, database, sources, SUCCESS,
                   logme)

from logme.database import DatabaseHandler
from os import makedirs
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse
import requests
import typer
from os import environ
from pathlib import Path
import pandas as pd
import time
import duolingo
from datetime import datetime

languages_dict = {'fr': 'Français'}

class DuolingoApi:
    """
    Class to call the unofficial duolingo api
    """

    def __init__(self, src: Path, dst: Path) -> None:
        self.src = src
        self.dst = dst
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

    def download(self) -> list:
        """
        Download the json file from Duoling
        :return: list of json activities
        """
        error = 0
        dst_path = Path(self.dst) / self.src
        if not dst_path.exists():
            makedirs(dst_path)
        load_dotenv('.env')
        user = environ.get('duolingo_user')
        password = environ.get('duolingo_pass')
        lingo = duolingo.Duolingo(user, password)
        learned_skills = lingo.get_learned_skills('fr')
        dst_file = Path(dst_path) / "learned_skills.json"
        # dst_file = Path(dst_path) / "learned_skills.pretty.2022_05_15.json"
        # data = open(dst_file)
        # learned_skills = json.load(data)
        with open(dst_file, "w") as f:
             dump(learned_skills, f)
        return learned_skills

    def process(self, learned_skills: list) -> pd.DataFrame:
        learned_skills_ts = []
        learned_skills_short = []
        learned_skills_language = []
        for skill in learned_skills:
            try:
                # print(skill['learned_ts'])
                learned_skills_ts.append(
                    # datetime.fromtimestamp(
                        int(skill['learned_ts'])
                    # )
                )
                learned_skills_short.append(
                    skill['short']
                )
                learned_skills_language.append(
                    languages_dict[skill['language']]
                )
            except KeyError:
                print("skill without learned_ts")
#        learned_skills_ts.insert(0, datetime.fromtimestamp(0))
#         learned_skills_ts.insert(0,int(0))
        df = pd.DataFrame(list(zip(learned_skills_ts,
                                   learned_skills_language,
                                   ['Duolingo'] * len(learned_skills_ts),
                                   learned_skills_short)),
                          columns=['ts_from','in_group','activity','comment'])
        df = df.sort_values('ts_from')
        df['ts_to'] = df['ts_from'].shift(-1)
        df['ts_to'] = df['ts_to'].fillna(int(datetime.now().timestamp()))
        df['ts_to'] = df['ts_to'].astype(int)
        df['duration_sec'] = (df['ts_to'] - df['ts_from']).astype(int)#.astype('timedelta64[s]')
        # df['ts_to'] = df['ts_to'].fillna(pd.to_datetime(0))
        # df['ts_from'] = pd.to_datetime(df['ts_from']).astype(int)/10**9
        # df['ts_to'] = pd.to_datetime(df['ts_to']).astype(int)/10**9
        df = df[['in_group','activity','comment','duration_sec','ts_from','ts_to']]
        df['hash'] = pd.Series((hash(tuple(row)) for
                                _,
                                row in df.iterrows()))
        df = df[['hash','in_group','activity','comment','duration_sec','ts_from','ts_to']]

        # Load previous learned_ts
        logme_df, err = self._db_handler.load_logme()
        print(f"logme_df: {logme_df.shape}")

        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        logme_df.columns = df.columns
        merged = df.merge(logme_df.drop_duplicates(),
                          on=['in_group', 'activity', 'comment',
                              'duration_sec', 'ts_from', 'ts_to'],
                          how='left', indicator=True)
        merged.rename(columns={'hash_x': 'hash'}, inplace=True)

        already_saved = merged[merged['_merge']=='both']
        to_save = merged[merged['_merge']!='both']
        to_save = to_save[df.columns]
        print(f"downloaded:     {df.shape}")
        print(f"merged:         {merged.shape}")
        print(f"already_saved:  {already_saved.shape}")
        print(f"To be inserted: {to_save.shape}")

        # db = merged.loc[merged['comment'].str.contains("Home"),['in_group', 'activity', 'comment','duration_sec','ts_from','ts_to']]
        # # db['ts_from'] = pd.to_datetime(db['ts_from'], unit='s')
        # # db['ts_to'] = pd.to_datetime(db['ts_to'], unit='s')
        # print('------ sql')
        # print(db)
        # bg = df.loc[df['comment'].str.contains("Home"),['in_group', 'activity', 'comment','duration_sec','ts_from','ts_to']]
        # # bg['ts_from'] = pd.to_datetime(bg['ts_from'], unit='s')
        # # bg['ts_to'] = pd.to_datetime(bg['ts_to'], unit='s')
        # print('------ api')
        # print(bg)
        # toS = to_save.loc[to_save['comment'].str.contains("Home"),['in_group', 'activity', 'comment','duration_sec','ts_from','ts_to']]
        # # toS['ts_from'] = pd.to_datetime(toS['ts_from'], unit='s')
        # # toS['ts_to'] = pd.to_datetime(toS['ts_to'], unit='s')
        # print('------ 2save')
        # print(toS)
        #
        # z=bg.merge(db.drop_duplicates(),
        #          on=['in_group', 'activity', 'comment',
        #              'duration_sec', 'ts_from', 'ts_to'],
        #          how='left', indicator=True)
        # print(z)
        print(to_save.to_string())
        return self._db_handler.write_logme(to_save)

