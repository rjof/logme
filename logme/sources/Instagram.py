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


class InstagramIngest:
    """Class to download saved posts"""

    # Create and configure logger
    logging.basicConfig(filename="03.log",
                        format='%(asctime)s %(message)s',
                        filemode='w')
                        # stream=sys.stdout)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Test messages
    logger.debug("Harmless debug Message")

TMPDIR = "../savedTmp"
EXTERNAL_HDD = "/media/rjof/toshiba/rjof/instagram/instaloader/saved/"
USER = environ.get('instagram_user')
PASSWORD = environ.get('instagram_password')
# USER = "errejotaoefe"
# PASSWORD = "w5A0#@ti7GvATesbNFj"
cookiefile = environ.get('firefox_cookiesfile') # clean "/home/rjof/snap/firefox/common/.mozilla/firefox/ycxcs1wp.default/cookies.sqlite"
sessionfile = environ.get('instaloader_sessionfile') # clean "/home/rjof/.config/instaloader/session-errejotaoefe"

def test_instagram():
    # driver = setup()

    # driver.implicitly_wait(2)

    # username_box = driver.find_element(by=By.NAME, value="username")
    # password_box = driver.find_element(by=By.NAME, value="password")
    
    # username_box.send_keys("errejotaoefe")
    # password_box.send_keys("w5A0#@ti7GvATesbNFi")
    # login_button = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
    # login_button.click()
    # driver.implicitly_wait(10)
    # driver.find_element(by=By.XPATH, value="//div[contains(string(), 'Not now')]").click()
    # driver.implicitly_wait(10)
    
    instaloader_import_session()
    assert 1 == 1
    # teardown(driver)

def instaloader_import_session():
    logger.info("################### Get session cookie form firefox #######################")
    # Connects using selenium
    driver = setup_selenium()

    # Refresh the instaloader session
    logger.info("Using cookies from {}.".format(cookiefile))
    conn = connect(f"file:{cookiefile}?immutable=1", uri=True)
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
    logger.info("Imported session cookie for {}.".format(username))
    L.context.username = username
    L.save_session_to_file(sessionfile)
    teardown(driver)

def setup_selenium():
    options = webdriver.FirefoxOptions()
    options.add_argument('--headless')
    service = webdriver.FirefoxService(executable_path="/snap/bin/geckodriver")
    driver = webdriver.Firefox(service=service, options=options)
    driver.get("https://www.instagram.com/accounts/login/")
    driver.implicitly_wait(2)
    username_box = driver.find_element(by=By.NAME, value="username")
    password_box = driver.find_element(by=By.NAME, value="password")
    username_box.send_keys(USER)
    password_box.send_keys(PASSWORD)
    login_button = driver.find_element(by=By.XPATH, value="//button[@type='submit']")
    login_button.click()
    driver.implicitly_wait(10)
    driver.find_element(by=By.XPATH, value="//div[contains(string(), 'Not now')]").click()
    driver.implicitly_wait(10)
    return driver

def teardown(driver):
    driver.quit()

def setup_instaloader():
    # Get instance
    L = instaloader.Instaloader(dirname_pattern=TMPDIR)

    # Optionally, login or load session
    # L.login(USER, PASSWORD)        # (login)
    # L.interactive_login(USER)      # (ask password on terminal)
    SESSION_FILE = "/home/rjof/.config/instaloader/session-errejotaoefe"
    L.load_session_from_file(USER, SESSION_FILE)
    testLogin = L.test_login()
    logger.info("Testing...")
    logger.info(f'testLogin: {testLogin}')
    return L


def instaloader_process(instaloader_session, driver_session):
    instaloader_session.download_saved_posts(1)
    files = glob.glob('*xz', root_dir=TMPDIR)
    urls = []
    for file in files:
        logger.info(file)
        jsonPost = lzma.open(f'{TMPDIR}/{file}').read().decode("utf-8")
        short_code = json.loads(jsonPost)
        post_url = f'https://www.instagram.com/p/{short_code["node"]["shortcode"]}/'
        urls.append(post_url)

    # Move to external hdd
    file_names = os.listdir(TMPDIR)
        
    for file_name in file_names:
        if not os.path.exists(os.path.join(EXTERNAL_HDD, file_name)):
            shutil.move(os.path.join(TMPDIR, file_name), os.path.join(EXTERNAL_HDD, file_name))
        else:
            os.remove(os.path.join(TMPDIR, file_name))

    # Remove from saved with selenium
    return unsave(urls, driver_session)


def instaloader_download(how_many):
    next = True
    instaloader_session = setup_instaloader()
    driver = setup_selenium() 
    while next:
    # for i in range(how_many):
        next = instaloader_process(instaloader_session,driver)
        logger.info(f'Will try to download another?: {next}')
    teardown(driver)


def unsave(urls, driver):
    next = False
    for url in urls:
        logger.info(f'Unsaving: {url}')
        driver.get(url)
        driver.implicitly_wait(10)
        try:
            save_botton = driver.find_element(By.XPATH, "//*[name()='svg' and @aria-label='Remove']")
            save_botton.click()
            next = True
        except:
            logger.info(f'Already unsaved: {url} or no more saved')
            next = False
    return next


# Command-line interface for the user
def main():
    parser = argparse.ArgumentParser(description="Download instagram saved posts.")
    parser.add_argument('-s', '--session', action=argparse.BooleanOptionalAction, help='Gets the session cookie from firefox and needs instagram session to be open in firefox')
    parser.add_argument('-c', '--count', type=int, help='How many saved posts to download')
    
    args = parser.parse_args()
    
    if args.session:
        instaloader_import_session()
    instaloader_download(args.count)


if __name__ == "__main__":
    main()
