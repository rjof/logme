import argparse
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
import json
import shutil
import os
from datetime import datetime
from itertools import dropwhile, takewhile
import instaloader
from sqlite3 import OperationalError, connect
import logging
from os import environ
# try:
#     from instaloader import ConnectionException, Instaloader
# except ModuleNotFoundError:
#     raise SystemExit("Instaloader not found.\n  pip install [--user] instaloader")
try:
    import lzma
except ImportError:
    from backports import lzma
import glob
from pathlib import Path
from logme import (config, database, SUCCESS, instagram_tmpdir, instagram_external_hdd, instagram_cookiefile, instagram_sessionfile)

class InstagramIngest:
    """Class to download saved posts"""

    logger = logging.getLogger(__name__)
    
    # Test messages
    logger.debug("Harmless debug Message")

    def __init__(self, src: Path, dst: Path) -> None:
        # TMPDIR = "../savedTmp"
        # EXTERNAL_HDD = "/media/rjof/toshiba/rjof/instagram/instaloader/saved/"
        self.USER = environ.get('instagram_user')
        self.logger.info(f'USER: {self.USER}')
        self.PASSWORD = environ.get('instagram_password')
        # USER = "errejotaoefe"
        # PASSWORD = "w5A0#@ti7GvATesbNFj"
        # cookiefile = environ.get('firefox_cookiesfile') # clean "/home/rjof/snap/firefox/common/.mozilla/firefox/ycxcs1wp.default/cookies.sqlite"
        # sessionfile = environ.get('instaloader_sessionfile') # clean "/home/rjof/.config/instaloader/session-errejotaoefe"
        self.src = src
        self.dst = dst
        self.SESSIONFILE = Path(instagram_sessionfile)
        

    def instaloader_import_session(self):
        self.logger.info("################### Get session cookie form firefox #######################")
        # Connects using selenium
        driver = setup_selenium()

        # Refresh the instaloader session
        self.logger.info("Using cookies from {}.".format(instagram_cookiefile))
        conn = connect(f"file:{instagram_cookiefile}?immutable=1", uri=True)
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
            raise SystemExit("Not logged in. Are you logged in successfully in Firefox?")
        self.logger.info("Imported session cookie for {}.".format(username))
        L.context.username = username
        L.save_session_to_file(self.SESSIONFILE)
        InstagramIngest.teardown(driver)

    def setup_selenium(self):
        options = webdriver.FirefoxOptions()
        options.add_argument('--headless')
        service = webdriver.FirefoxService(executable_path="/snap/bin/geckodriver")
        driver = webdriver.Firefox(service=service, options=options)
        driver.get("https://www.instagram.com/accounts/login/")
        driver.implicitly_wait(2)
        username_box = driver.find_element(by=By.NAME, value="username")
        password_box = driver.find_element(by=By.NAME, value="password")
        username_box.send_keys(self.USER)
        password_box.send_keys(self.PASSWORD)
        login_button = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
        login_button.click()
        driver.implicitly_wait(10)
        driver.find_element(by=By.XPATH, value="//div[contains(string(), 'Not now')]").click()
        driver.implicitly_wait(10)
        return driver

    def teardown(driver):
        driver.quit()

    def setup_instaloader(self):
        # Get instance
        L = instaloader.Instaloader(dirname_pattern=instagram_tmpdir)

        # Optionally, login or load session
        # L.login(USER, PASSWORD)        # (login)
        # L.interactive_login(USER)      # (ask password on terminal)
        # SESSION_FILE = "/home/rjof/.config/instaloader/session-errejotaoefe"
        L.load_session_from_file(self.USER, Path("/home/rjof/.config/instaloader/session-errejotaoefe"))
        testLogin = L.test_login()
        self.logger.info("Testing...")
        self.logger.info(f'testLogin: {testLogin}')
        return L


    def instaloader_process(self,instaloader_session, driver_session):
        instaloader_session.download_saved_posts(1)
        files = glob.glob('*xz', root_dir=instagram_tmpdir)
        urls = []
        for file in files:
            self.logger.info(file)
            jsonPost = lzma.open(f'{instagram_tmpdir}/{file}').read().decode("utf-8")
            short_code = json.loads(jsonPost)
            post_url = f'https://www.instagram.com/p/{short_code["node"]["shortcode"]}/'
            urls.append(post_url)

        # Move to external hdd
        file_names = os.listdir(instagram_tmpdir)
            
        for file_name in file_names:
            if not os.path.exists(os.path.join(instagram_external_hdd, file_name)):
                shutil.move(os.path.join(instagram_tmpdir, file_name), os.path.join(instagram_external_hdd, file_name))
            else:
                os.remove(os.path.join(instagram_tmpdir, file_name))

        # Remove from saved with selenium
        return self.unsave(urls, driver_session)


    def instaloader_download(self, how_many):
        next = True
        instaloader_session = self.setup_instaloader()
        driver = self.setup_selenium() 
        while next:
        # for i in range(how_many):
            next = self.instaloader_process(instaloader_session,driver)
            self.logger.info(f'Will try to download another?: {next}')
        InstagramIngest.teardown(driver)


    def unsave(self,urls, driver):
        next = False
        for url in urls:
            self.logger.info(f'Unsaving: {url}')
            driver.get(url)
            driver.implicitly_wait(10)
            try:
                save_botton = driver.find_element(By.XPATH, "//*[name()='svg' and @aria-label='Remove']")
                save_botton.click()
                next = True
            except:
                self.logger.info(f'Already unsaved: {url} or no more saved')
                next = False
        return next

class InstagramProcess:
    pass
    

def test_instagram():
    driver = InstagramIngest.setup()

    driver.implicitly_wait(2)

    username_box = driver.find_element(by=By.NAME, value="username")
    password_box = driver.find_element(by=By.NAME, value="password")
    
    username_box.send_keys("errejotaoefe")
    password_box.send_keys("w5A0#@ti7GvATesbNFi")
    login_button = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
    login_button.click()
    driver.implicitly_wait(10)
    driver.find_element(by=By.XPATH, value="//div[contains(string(), 'Not now')]").click()
    driver.implicitly_wait(10)
    
    InstagramIngest.instaloader_import_session()
    assert 1 == 1
    InstagramIngest.teardown(driver)

# Command-line interface for the user
def main():
    parser = argparse.ArgumentParser(description="Download instagram saved posts.")
    parser.add_argument('-s', '--session', action=argparse.BooleanOptionalAction, help='Gets the session cookie from firefox and needs instagram session to be open in firefox')
    parser.add_argument('-c', '--count', type=int, help='How many saved posts to download')
    
    args = parser.parse_args()
    
    if args.session:
        InstagramIngest.instaloader_import_session()
    InstagramIngest.instaloader_download(args.count)


if __name__ == "__main__":
    main()
