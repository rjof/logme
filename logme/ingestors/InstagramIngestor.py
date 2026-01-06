from logme.storage.database import DatabaseHandler
import argparse
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
import json, glob, shutil, os, instaloader, logging, typer
from datetime import datetime
from itertools import dropwhile, takewhile

# from sqlite3 import OperationalError, connect
from os import environ
from logme.ddl.InstagramRow import InstagramRow

# try:
#     from instaloader import ConnectionException, Instaloader
# except ModuleNotFoundError:
#     raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")
try:
    import lzma
except ImportError:
    from backports import lzma
from pathlib import Path
import pandas as pd

from logme.utils.Utils import get_database_path
from logme import (
    config,
    SUCCESS,
    now_ts,
)  # , instagram_tmpdir, instagram_external_hdd, instagram_cookiefile, instagram_sessionfile)

# from logme.storage.database import *
from logme.utils import ProcessingUtils
import logme.utils.Utils as u


class InstagramIngestor:
    """Class to download saved posts"""

    def __init__(self, src: Path, conf: dict) -> None:
        self.src = src
        self.conf = conf
        self.conf_landing_to_raw = u.get_source_conf(
            self.src, f"{self.src}_landing_to_raw"
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Starting InstagramIngest")
        # TMPDIR = "../savedTmp"
        # EXTERNAL_HDD = "/media/rjof/toshiba/rjof/instagram/instaloader/saved/"
        self.USER = environ.get("instagram_user")
        self.logger.info(f"USER: {self.USER}")
        self.PASSWORD = environ.get("instagram_password")
        # USER = "errejotaoefe"
        # PASSWORD = "w5A0#@ti7GvATesbNFj"
        # cookiefile = environ.get('firefox_cookiesfile') # clean "/home/rjof/snap/firefox/common/.mozilla/firefox/ycxcs1wp.default/cookies.sqlite"
        # sessionfile = environ.get('instaloader_sessionfile') # clean "/home/rjof/.config/instaloader/session-errejotaoefe"
        self.SESSIONFILE = Path(self.conf["sessionfile"])
        if ProcessingUtils._table_exists(f"{self.src}_raw") != True:
            self.logger.info(f"Creating raw table {self.src}_raw")
            query = ProcessingUtils._query_from_list_of_fields(
                self.src, "raw", self.conf["fields"], self.conf["fields_format"]
            )
            # print(query)
            if ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_raw")

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
        self._db_handler = DatabaseHandler(db_path)

    def instaloader_import_session(self):
        self.logger.info(
            "################### Get session cookie form firefox #######################"
        )
        # Connects using selenium
        driver = self.setup_selenium()

        # Refresh the instaloader session
        self.logger.info("Using cookies from {}.".format(self.conf["cookiefile"]))
        conn = connect(f"file:{self.conf['cookiefile']}?immutable=1", uri=True)
        try:
            cookie_data = conn.execute(
                "SELECT name, value FROM moz_cookies WHERE baseDomain='instagram.com'"
            )
        except OperationalError:
            cookie_data = conn.execute(
                "SELECT name, value FROM moz_cookies WHERE host LIKE '%instagram.com'"
            )
        L = instaloader.Instaloader(max_connection_attempts=1)
        L.context._session.cookies.update(cookie_data)
        username = L.test_login()
        if not username:
            raise SystemExit(
                "Not logged in. Are you logged in successfully in Firefox?"
            )
        self.logger.info("Imported session cookie for {}.".format(username))
        L.context.username = username
        L.save_session_to_file(self.SESSIONFILE)
        InstagramIngestor.teardown(driver)

    def setup_selenium(self):
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        service = webdriver.FirefoxService(executable_path="/snap/bin/geckodriver")
        driver = webdriver.Firefox(service=service, options=options)
        driver.get("https://www.instagram.com/accounts/login/")
        driver.implicitly_wait(2)
        username_box = driver.find_element(by=By.NAME, value="username")
        password_box = driver.find_element(by=By.NAME, value="password")
        username_box.send_keys(self.USER)
        password_box.send_keys(self.PASSWORD)
        login_button = driver.find_element(
            by=By.XPATH, value="//button[@type='submit']"
        )
        login_button.click()
        driver.implicitly_wait(10)
        driver.find_element(
            by=By.XPATH, value="//div[contains(string(), 'Not now')]"
        ).click()
        driver.implicitly_wait(10)
        return driver

    def teardown(driver):
        driver.quit()

    def setup_instaloader(self):
        # Get instance
        L = instaloader.Instaloader(dirname_pattern=self.conf["tmpdir"])

        # Optionally, login or load session
        # L.login(USER, PASSWORD)        # (login)
        # L.interactive_login(USER)      # (ask password on terminal)
        # L.load_session_from_file(self.USER, Path("/home/rjof/.config/instaloader/session-errejotaoefe"))
        L.load_session_from_file(self.USER, self.SESSIONFILE)
        testLogin = L.test_login()
        self.logger.info("Testing...")
        self.logger.info(f"testLogin: {testLogin}")
        return L

    def instaloader_download(self, how_many):
        next = True
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        if len(files) == 0:
            offline = False
        else:
            offline = True
        # Clear comment
        # instaloader_session = self.setup_instaloader()
        # driver = self.setup_selenium()
        if not offline:
            self.logger.info("Processing on line saved")
            # while next:
            for i in range(how_many):
                next = self.instaloader_process(instaloader_session, driver)
            InstagramIngestor.teardown(driver)
        else:
            self.logger.info("Processing off line already downloaded")
            urls = self.instaloader_process_downloaded()
            self.move_to_exteranl_hdd()
            self.unsave(urls, driver)
            # instaloader_session = None
            # driver = None


    def instaloader_process_downloaded(self) -> list[str]:
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        urls = []
        merged = None
        dfs = []
        for file in files:
            self.logger.info(f"Processing: {file}")
            self.logger.info(f"instaloader_process_offline: {file}")
            tmpdir = self.conf["tmpdir"]
            jsonPost = lzma.open(f"{tmpdir}/{file}").read().decode("utf-8")
            json_obj = json.loads(jsonPost)
            df1 = pd.json_normalize(json_obj)
            df1_cols = sorted(set(df1.columns))
            dfs.append(df1)
            print(f"df1 # cols: {len(df1.columns)}")
            print(f"df1 set # cols: {len(df1_cols)}")
            # table exists?
            table_name="instagram_raw_2"
            table_exists = ProcessingUtils._table_exists(table_name=table_name)
            print(f"table exists: {table_exists}")
            pd.set_option('display.max_columns', 1000)
            pd.set_option('display.expand_frame_repr', True) 
            import numpy as np
            # Convert to string but restore actual NaNs
            df1 = df1.astype(str).replace('nan', np.nan)
            # print(df1.iloc[0].to_string())
            # print(df1.info())
            # print(df1.dtypes)
            if not table_exists:
                self._db_handler.df_to_db(df=df1, table_name=table_name)
            else:
                print("Get all field names in database")
                cols_in_db = self._db_handler.fields_in_table(table_name)
                print(f"{len(cols_in_db)} columns in database")
                if set(df1.columns) == set(cols_in_db):
                    print(f"Equal set of columns => save row")
                else:
                    print(f"Columns differ. Alter table")
                    new_columns = [key for key in df1_cols if key not in cols_in_db]
                    print("Different columns")
                    print(new_columns)
                    for new_col in new_columns:
                        self._db_handler.alter_table(table_name=table_name, new_col=new_col)
                    cols_in_db = self._db_handler.fields_in_table(table_name)
                    print(f"{len(cols_in_db)} columns in database after alter")
                    placeholders = ', '.join(['?' for _ in cols_in_db])
                    quoted_columns = ', '.join([f'"{col}"' for col in cols_in_db])
                    values = [df1[col].iloc[0] if col in df1_cols else np.nan for col in cols_in_db]
                    # print(f"Placeholders:\n{placeholders}")
                    # print(f"quoted_columns:\n{quoted_columns}")
                    # print(f"values:\n{values}")
                    self._db_handler.row_to_raw_instagram(table_name=table_name,
                                                          placeholders=placeholders,
                                                          quoted_columns=quoted_columns,
                                                          values=values)
        
        # merged_df = pd.concat(dfs,ignore_index=True)
        # print(f"# all cols: {len(merged_df.columns)}")
        exit(3)


            # data = self.instaloader_landing_to_raw(jsonPost)
            # data = pd.DataFrame([data])
            # data["src_file"] = file
            # data["ingest_timestamp"] = now_ts
            # data["hash"] = data.at[0,"shortcode"]

            # # TODO:
            # # Field *hash* in instagram_raw is unique
            # # If the raw was saved but the post was not
            # for index, row in data.iterrows():

            #     # print(f'created_at: {row["created_at"]}')
            #     # print(f'text: {row["text"]}')
            #     # print(f'shortcode: {row["shortcode"]}')
            #     # print(f'comment_count: {row["comment_count"]}')
            #     # print(f'edge_liked_by: {row["edge_liked_by"]}')
            #     # print(f'owner_id: {row["owner_id"]}')
            #     # print(f'username: {row["username"]}')
            #     # print(f'edge_followed_by: {row["edge_followed_by"]}')
            #     # print(f'src_file: {row["src_file"]}')
            #     # print(f'ingest_timestamp: {["ingest_timestamp"]}')
            #     # print(f'hash: {row["hash"]}')

            #     new_post = InstagramRow(
            #         created_at=row["created_at"],
            #         text=row["text"],
            #         shortcode=row["shortcode"],
            #         comment_count=row["comment_count"],
            #         edge_liked_by=row["edge_liked_by"],
            #         owner_id=row["owner_id"],
            #         username=row["username"],
            #         edge_followed_by=row["edge_followed_by"],
            #         src_file=file,
            #         ingest_timestamp=now_ts,
            #         hash=row["hash"],
            #     )
            #     res = self._db_handler.raw_instagram_row_to_db(new_post)

            # # res = self._db_handler.df_to_db(data, f'{self.src}_raw')
            # # prompt = input(f"Short code: {data['shortcode']}")
            # post_url = f'https://www.instagram.com/p/{data.at[0,"shortcode"]}/'
            # print(f"post_url {post_url}")
            # print(f"urls: {urls}")
            # urls.append(post_url)
        return urls


    def _find_key_paths(self,data, target_key, current_path=None):
        """
        Finds all paths to a target_key in a nested dictionary or list.

        Args:
            data (dict or list): The nested data structure to search.
            target_key: The key to find.
            current_path (list, optional): The current path taken to reach the
            current level of recursion. Defaults to None.

        Yields:
            tuple: A tuple representing the path to the target_key.
        """
        if current_path is None:
            current_path = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = current_path + [key]
                if key == target_key:
                    yield tuple(new_path)
                if isinstance(value, (dict, list)):
                    yield from self._find_key_paths(value, target_key, new_path)
        elif isinstance(data, list):
            for index, item in enumerate(data):
                new_path = current_path + [index]
                if isinstance(item, (dict, list)):
                    yield from self._find_key_paths(item, target_key, new_path)


    def _instaloader_json_path_exists(self, field, post) -> str:
        path=self.conf_landing_to_raw[field].split(",")
        path_length=len(path)
        print(f"Looking for data under:")
        print(path)
        print(f"With length: {path_length}")
        json_obj = json.loads(post)
        vals=[]
        for e1 in self._find_key_paths(json_obj,field):
            # If the lenght in the config equals the one
            # in e1 the match is "perfect"
            print("Found path")
            print(e1)
            print(len(e1))
            if len(e1) == path_length:
                print(f"The path found in the json is exact")
            elif path_length < len(e1):
                print(f"Found longer path. Good candidate")
            elif path_length > len(e1):
                print(f"The found path is smaller. Not a good candidate")
        exit(3)
            # o1=json_obj
            # for k1 in e1:
            #     if isinstance(k1,int):
            #         k1=int(k1)
            #     o1=o1[k1]
            # vals.append(o1)
        return vals


    def instaloader_landing_to_raw(self, post) -> dict:
        """
        In the section instagram_landing_to_raw of the instagram.ini file
        the expected path is stated for the data to be saved.
        Some times the data is not there, so this contains the heuristic
        to decide
        """
        # landing to raw
        values = {}
        for field in self.conf_landing_to_raw:
            res1 = self._instaloader_json_path_exists(field, post)
            if len(str(res1)) > 0:
                values[field] = res1
            else:
                values[field] = None
        return values

    def instaloader_process(self, instaloader_session, driver_session):
        # downloads one saved post to self.conf['tmpdir']
        res = instaloader_session.download_saved_posts(1)
        urls = self.instaloader_process_downloaded()
        self.move_to_exteranl_hdd()

        # Remove from saved with selenium
        offensive_urls = [
            "https://www.instagram.com/p/C_b6n8Ttq05/",
            "https://www.instagram.com/p/C_b6oJTNrqG/",
        ]
        for url in offensive_urls:
            if url in urls:
                urls.remove(url)
        return self.unsave(urls, driver_session)

    def move_to_exteranl_hdd(self):
        # Move to external hdd
        file_names = os.listdir(self.conf["tmpdir"])
        for file_name in file_names:
            if not os.path.exists(os.path.join(self.conf["external_hdd"], file_name)):
                shutil.move(
                    os.path.join(self.conf["tmpdir"], file_name),
                    os.path.join(self.conf["external_hdd"], file_name),
                )
            else:
                os.remove(os.path.join(self.conf["tmpdir"], file_name))

    def unsave(self, urls, driver):
        next = False
        for url in urls:
            self.logger.info(f"Unsaving: {url}")
            driver.get(url)
            driver.implicitly_wait(10)
            try:
                save_botton = driver.find_element(
                    By.XPATH, "//*[name()='svg' and @aria-label='Remove']"
                )
                save_botton.click()
                next = True
            except:
                self.logger.info(f"Already unsaved: {url} or no more saved")
                next = False
        return next


def test_instagram():
    driver = InstagramIngestor.setup()

    driver.implicitly_wait(2)

    username_box = driver.find_element(by=By.NAME, value="username")
    password_box = driver.find_element(by=By.NAME, value="password")

    username_box.send_keys("errejotaoefe")
    password_box.send_keys("w5A0#@ti7GvATesbNFi")
    login_button = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
    login_button.click()
    driver.implicitly_wait(10)
    driver.find_element(
        by=By.XPATH, value="//div[contains(string(), 'Not now')]"
    ).click()
    driver.implicitly_wait(10)

    InstagramIngestor.instaloader_import_session()
    assert 1 == 1
    InstagramIngestor.teardown(driver)


# def main():
#     parser = argparse.ArgumentParser(description="Download instagram saved posts.")
#     parser.add_argument(
#         "-s",
#         "--session",
#         action=argparse.BooleanOptionalAction,
#         help="Gets the session cookie from firefox and needs instagram session to be open in firefox",
#     )
#     parser.add_argument(
#         "-c", "--count", type=int, required=True, help="How many saved posts to download"
#     )

#     args = parser.parse_args()

#     if args.session:
#         InstagramIngest.instaloader_import_session()
#     InstagramIngest.instaloader_download(args.count)


# if __name__ == "__main__":
#     main()
