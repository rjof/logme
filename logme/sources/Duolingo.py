import json
import sys
from dotenv import load_dotenv
from json import load, dump
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
from logme import (config, database, sources,
                   SUCCESS, duolingo_languages, duolingo_end_points, logme)
from logme.database import DatabaseHandler
from logme.utils import str_to_class

languages_dict = {'fr': 'Français', 'de': 'Deutsch'}


class DuolingoApi:
    """
    Class to call the unofficial duolingo api
    """

    def __init__(self, src: Path, dst: Path) -> None:
        self.src = src
        self.dst = dst
        now = datetime.now()  # current date and time
        self.date_time = now.strftime("%Y-%m-%d_%H-%M-%S")
        print("date and time:", self.date_time)

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
        error = 0
        self.download_end_points()

    def download_end_points(self) -> None:
        """
        Download the json file from Duolingo
        :return: list of json activities
        """
        dst_path = Path(self.dst) / self.src / f"{self.date_time}"
        if not dst_path.exists():
            makedirs(dst_path)
        load_dotenv('.env')
        user = environ.get('duolingo_user')
        print(f"user (duolingo): {user}")
        #password = environ.get('duolingo_pass')
        jwt = environ.get('duolingo_jwt')
        print(f"jwt: {jwt}")
        # Deprecated because of dulingo changes
        #lingo = duolingo.Duolingo(user, password)
        lingo = duolingo.Duolingo(user, jwt=jwt)
        # Before downloading skills need to be in that language
        # by lingo._switch_language (french fr, deutsch de)

        cal = str(lingo.get_calendar()).replace(
            "None", "'None'").replace("'", '"')
        dst_file = dst_path / "cal.json"
        with open(dst_file, "w") as f:
            dump(cal, f)
        # steak = lingo.get_streak_info()
        # This is a very good daily update
        # @todo

        for language in duolingo_languages:
            print(f"language in config: {language}")
            lingo._switch_language(language)
            dst_path_language = dst_path / f"{language}"
            if not dst_path_language.exists():
                makedirs(dst_path_language)

            end_point_functions = ["lingo.get_" +
                sub for sub in duolingo_end_points]
            for end_point in end_point_functions:
                dst_file = dst_path_language / f"{end_point}.json"
                if "leaderboard" in end_point:
                     data = eval(f"{end_point}")('wee,', time.time())
                else:
                    data = eval(f"{end_point}")(language)
                with open(dst_file, "w") as f:
                    dump(data, f)
            # golden = lingo.get_golden_topics(language)
            # reviewable = lingo.get_reviewable_topics(language)
            # known_words = lingo.get_known_words(language)
            # language_details = lingo.get_language_details(
            #     lingo.get_language_from_abbr(language))

            # Very long
            # vocabulary = lingo.get_vocabulary(language_abbr=language)
            # Takes forever... not useful for training
            # print(lingo.get_audio_url('bonjour'))
            # Very long with explanations and html in the middle
            # print(lingo.get_learned_skills(language))
            # Usable in other context like training with a speaker
            #  print(lingo.get_related_words('aller'))
            #  lingo.get_translations(['de', 'du'], source='de', target='fr')
            # Broken:
            # File "/home/rjof/python_envs/logme_env/lib/python3.10/site-packages/duolingo.py",
            # line 272, in _make_dict
            # data[key] = array[key]
            # KeyError: 'points_rank'
            # print(lingo.get_language_progress(language))
            # Broken:
            # print(lingo.buy_streak_freeze())
            # Broken:
            # print(lingo.buy_item('streak_freeze', language))
            # Broken:
            # File "/home/rjof/python_envs/logme_env/lib/python3.10/site-packages/duolingo.py",
            # line 407, in get_friends
            # for friend in v['points_ranking_data']:
            # KeyError: 'points_ranking_data'
            # print(lingo.get_leaderboard('week',time.time()))

        exit(0)

        # lingo._switch_language(language)
        # learned_skills = lingo.get_learned_skills(language)
        # dst_file = dst_path / f"{language}.json"
        # # dst_file = Path(dst_path) / "learned_skills.pretty.2022_05_15.json"
        # # data = open(dst_file)
        # # learned_skills = json.load(data)
        # with open(dst_file, "w") as f:
        #     dump(learned_skills, f)
        #     return learned_skills

        # At what time is it refreshed?
        # xp_progress = lingo.get_daily_xp_progress()

        # skills = self.download(language, lingo, dst_path)
        # self.process(learned_skills=skills)

    def download(self, language, lingo, dst_path) -> list:
        """
        Download the json file from Duoling
        :return: list of json activities
        """
        lingo._switch_language(language)
        learned_skills = lingo.get_learned_skills(language)
        dst_file = dst_path / f"{language}.json"
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
                # print(skill['language'])
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
                          columns=['ts_from', 'in_group', 'activity', 'comment'])
        df = df.sort_values('ts_from')
        df['ts_to'] = df['ts_from'].shift(-1)
        df['ts_to'] = df['ts_to'].fillna(int(datetime.now().timestamp()))
        df['ts_to'] = df['ts_to'].astype(int)
        # .astype('timedelta64[s]')
        df['duration_sec'] = (df['ts_to'] - df['ts_from']).astype(int)
        # df['ts_to'] = df['ts_to'].fillna(pd.to_datetime(0))
        # df['ts_from'] = pd.to_datetime(df['ts_from']).astype(int)/10**9
        # df['ts_to'] = pd.to_datetime(df['ts_to']).astype(int)/10**9
        df = df[['in_group', 'activity', 'comment',
                 'duration_sec', 'ts_from', 'ts_to']]
        df['hash'] = pd.util.hash_pandas_object(df)
        # Change type from unit64 to object
        df['hash'] = df['hash'].astype(str)
        df = df[['hash', 'in_group', 'activity', 'comment',
                 'duration_sec', 'ts_from', 'ts_to']]

        # Load previous learned_ts
        logme_df, err = self._db_handler.load_logme()
        print(f"logme_df: {logme_df.shape}")

        if err != SUCCESS:
            msg = f"The database was not found or readable."
            raise Exception(msg)
        merged = df.merge(
            logme_df.drop_duplicates(),
            on=['in_group', 'activity', 'comment',
                'duration_sec', 'ts_from', 'ts_to'],
            how='left', indicator=True)
        merged.rename(columns={'hash_x': 'hash'}, inplace=True)

        already_saved = merged[merged['_merge'] == 'both']
        to_save = merged[merged['_merge'] != 'both']
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
