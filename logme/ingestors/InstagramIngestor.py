from logme.storage.database import DatabaseHandler
import argparse, numpy as np, sys
from selenium import webdriver
from selenium.webdriver.common.by import By
import json, glob, shutil, os, instaloader, logging, typer, time
from datetime import datetime
from itertools import dropwhile, takewhile

from sqlite3 import OperationalError, connect
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
import logme.utils.Utils as u


class InstagramIngestor:
    """Class to download saved posts"""

    def __init__(self, src: Path, conf: dict) -> None:
        from logme.utils import ProcessingUtils
        self.ProcessingUtils = ProcessingUtils
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
        if self.ProcessingUtils._table_exists(f"{self.src}_raw") != True:
            self.logger.info(f"Creating raw table {self.src}_raw")
            query = self.ProcessingUtils._query_from_list_of_fields(
                self.src, "raw", self.conf["fields"], self.conf["fields_format"]
            )
            # print(query)
            if self.ProcessingUtils._create_table(query) != SUCCESS:
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

    def instaloader_download(self, how_many):
        next = True
        offline = self._is_working_offline()
        instaloader_session = self.setup_instaloader()
        driver = self.setup_selenium()
        try:
            if not offline:
                self.logger.info("Processing on line saved")
                for i in range(how_many):
                    next = self.instaloader_process(instaloader_session, driver)
            else:
                self.logger.info("Processing off line already downloaded")
                urls = self.instaloader_process_downloaded()
                self.move_to_exteranl_hdd()
                self.unsave(urls, driver)
        finally:
            InstagramIngestor.teardown(driver)

    def setup_selenium(self):
        self.logger.info("Setting up Selenium with injected cookies...")
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        service = webdriver.FirefoxService(executable_path="/snap/bin/geckodriver")
        driver = webdriver.Firefox(service=service, options=options)
        driver.set_page_load_timeout(60)
        
        try:
            # Set domain context
            driver.get("https://www.instagram.com/")
            time.sleep(3)
            
            # Inject cookies from Firefox profile
            cookie_db = self.conf["cookiefile"]
            if os.path.exists(cookie_db):
                self.logger.info(f"Injecting cookies from {cookie_db}")
                # Use a temporary copy to avoid locking issues
                temp_db = "temp_cookies_selenium.sqlite"
                shutil.copy(cookie_db, temp_db)
                
                import sqlite3
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT name, value, host, path, expiry FROM moz_cookies WHERE host LIKE '%instagram.com'")
                cookies = cursor.fetchall()
                conn.close()
                os.remove(temp_db)
                
                for name, value, host, path, expiry in cookies:
                    cookie_dict = {
                        'name': name,
                        'value': value,
                        'domain': host,
                        'path': path,
                    }
                    try:
                        driver.add_cookie(cookie_dict)
                    except:
                        pass
                self.logger.info("Cookies injected.")
            else:
                self.logger.warning(f"Cookie file not found: {cookie_db}. Attempting manual login.")
                # Fallback to manual login if needed
                driver.get("https://www.instagram.com/accounts/login/")
                driver.implicitly_wait(10)
                username_box = driver.find_element(by=By.NAME, value="email")
                password_box = driver.find_element(by=By.NAME, value="pass")
                username_box.send_keys(self.USER)
                password_box.send_keys(self.PASSWORD)
                login_button = driver.find_element(by=By.XPATH, value='//*[@aria-label="Log In"]')
                login_button.click()
                time.sleep(5)
        except Exception as e:
            self.logger.error(f"Error in setup_selenium: {e}")
            
        return driver

    @staticmethod
    def teardown(driver):
        if driver:
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

    def _is_working_offline(self):
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        if len(files) == 0:
            return False
        else:
            return True

    def instaloader_process_downloaded(self) -> list[str]:
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        urls = []
        for file in files:
            self.logger.info(f"Processing: {file}")
            self.logger.info(f"instaloader_process_offline: {file}")
            tmpdir = self.conf["tmpdir"]
            jsonPost = lzma.open(f"{tmpdir}/{file}").read().decode("utf-8")
            json_obj = json.loads(jsonPost)
            df1 = pd.json_normalize(json_obj).reset_index(drop=True)
            df1.insert(loc=0, column="ingest_timestamp", value=now_ts)
            df1.insert(loc=0, column="src_file", value=file)
            df1_cols = sorted(set(df1.columns))
            print(f"df1 # cols: {len(df1.columns)}")
            print(f"df1 set # cols: {len(df1_cols)}")
            # table exists?
            table_name = "instagram_raw_2"
            table_exists = self.ProcessingUtils._table_exists(table_name=table_name)
            print(f"table exists: {table_exists}")
            # pd.set_option('display.max_columns', 1000)
            # pd.set_option('display.expand_frame_repr', True)
            # Convert to string but restore actual NaNs
            df1 = df1.astype(str).replace("nan", np.nan)
            print(df1.head())
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
                    # print("Different columns")
                    # print(new_columns)
                    for new_col in new_columns:
                        self._db_handler.alter_table(
                            table_name=table_name, new_col=new_col
                        )
                    cols_in_db = self._db_handler.fields_in_table(table_name)
                    print(f"{len(cols_in_db)} columns in database after alter")
                placeholders = ", ".join(["?" for _ in cols_in_db])
                quoted_columns = ", ".join([f'"{col}"' for col in cols_in_db])
                values = [
                    df1[col].iloc[0] if col in df1_cols else np.nan
                    for col in cols_in_db
                ]
                print(f'cols_in_db: {cols_in_db.index("node.shortcode")}')
                print(
                    f"""
{values[cols_in_db.index("node.shortcode")]}: {df1['node.shortcode'].iloc[0]}
                      """
                )
                shortcode_value = df1["node.shortcode"].iloc[0]
                print(f"values (shortcode): {shortcode_value}")
                # print(f"values (shortcode): {values[{df1['node.shortcode']}]}")
                # print(f"values (shortcode): {df1['node.shortcode']}")
                self._db_handler.row_to_raw_instagram(
                    table_name=table_name,
                    placeholders=placeholders,
                    quoted_columns=quoted_columns,
                    values=values,
                )
            post_url = f'https://www.instagram.com/p/{df1["node.shortcode"].iloc[0]}/'
            urls.append(post_url)
            print(f"post_url {post_url}")
            print(f"urls: {urls}")

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
        return urls

    def _find_key_paths(self, data, target_key, current_path=None):
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
        path = self.conf_landing_to_raw[field].split(",")
        path_length = len(path)
        print(f"Looking for data under:")
        print(path)
        print(f"With length: {path_length}")
        json_obj = json.loads(post)
        vals = []
        for e1 in self._find_key_paths(json_obj, field):
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
            print(f"Moving {file_name} to {self.conf['external_hdd']}")
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
            print(f"Unsaving: {url}")
            driver.get(url)
            time.sleep(5)
            try:
                # Multiple common selectors for Instagram's save/unsave button
                selectors = [
                    "//*[name()='svg' and @aria-label='Remove']",
                    "//*[name()='svg' and @aria-label='Unsave']",
                ]
                
                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.XPATH, selector)
                        if not elements:
                            continue
                        
                        element = elements[0]
                        aria_label = element.get_attribute("aria-label")
                        self.logger.info(f"Found {aria_label} button.")
                        
                        # Try to find the actual clickable button (ancestor)
                        clickable = element.find_element(By.XPATH, "./ancestor::div[@role='button'] | ./ancestor::button")
                        clickable.click()
                        self.logger.info(f"Successfully clicked {aria_label} button.")
                        next = True
                        time.sleep(2)
                        break
                    except:
                        continue
            except Exception as e:
                self.logger.error(f"Error during unsave for {url}: {e}")
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
