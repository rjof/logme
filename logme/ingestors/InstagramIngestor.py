from logme.storage.database import DatabaseHandler
import argparse, numpy as np, sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json, glob, shutil, os, instaloader, logging, typer, time
from datetime import datetime
from itertools import dropwhile, takewhile

from sqlite3 import OperationalError, connect
from os import environ
from logme.ddl.InstagramRow import InstagramRow
from selenium.webdriver.firefox.service import Service as FirefoxService

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
)
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
        self.USER = environ.get("instagram_user")
        self.logger.info(f"USER: {self.USER}")
        self.PASSWORD = environ.get("instagram_password")
        self.SESSIONFILE = Path(self.conf["sessionfile"])
        
        if self.ProcessingUtils._table_exists(f"{self.src}_raw") != True:
            self.logger.info(f"Creating raw table {self.src}_raw")
            query = self.ProcessingUtils._query_from_list_of_fields(
                self.src, "raw", self.conf["fields"], self.conf["fields_format"]
            )
            if self.ProcessingUtils._create_table(query) != SUCCESS:
                raise typer.Exit(f"Error creating {self.src}_raw")

        if config.CONFIG_FILE_PATH.exists():
            db_path = get_database_path(config.CONFIG_FILE_PATH)
        else:
            typer.secho('Config file not found. Please, run "logme init"', fg=typer.colors.RED)
            raise typer.Exit(1)
            
        if not db_path.exists():
            typer.secho('Database not found. Please, run "logme init"', fg=typer.colors.RED)
            raise typer.Exit(1)
        self._db_handler = DatabaseHandler(db_path)

    def instaloader_import_session(self, driver=None):
        self.logger.info("Refreshing Instaloader session from Selenium...")
        close_driver = False
        if driver is None:
            driver = self.setup_selenium()
            close_driver = True
        
        if not self._is_logged_in(driver):
            self.logger.error("Selenium is not logged in. Cannot refresh Instaloader session.")
            if close_driver: self.teardown(driver)
            return False

        self.logger.info("Selenium is logged in, transferring cookies to Instaloader...")
        L = instaloader.Instaloader()
        for cookie in driver.get_cookies():
            L.context._session.cookies.set(
                cookie['name'], 
                cookie['value'], 
                domain=cookie['domain'], 
                path=cookie['path']
            )
        
        username = L.test_login()
        if username:
            self.logger.info(f"Instaloader session successfully refreshed for {username}")
            self.USER = username # Update instance USER
            L.save_session_to_file(self.SESSIONFILE)
            if close_driver: self.teardown(driver)
            return True
        else:
            self.logger.error("Instaloader failed to validate cookies from Selenium.")
            if close_driver: self.teardown(driver)
            return False

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
        browser = self.conf.get("browser", "firefox").lower()
        self.logger.info(f"Setting up Selenium with {browser}...")
        
        if browser == "chrome":
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            options = ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            chrome_path = None
            for path in ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver", "/snap/bin/chromedriver"]:
                if os.path.exists(path):
                    chrome_path = path
                    break
            
            if chrome_path:
                self.logger.info(f"Using chromedriver at {chrome_path}")
                service = ChromeService(executable_path=chrome_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                self.logger.info("Chromedriver not found in common paths, relying on system PATH")
                driver = webdriver.Chrome(options=options)
        else:
            options = webdriver.FirefoxOptions()
            options.add_argument("--headless")
            gecko_path = None
            for path in ["/usr/local/bin/geckodriver", "/snap/bin/geckodriver", "/usr/bin/geckodriver"]:
                if os.path.exists(path):
                    gecko_path = path
                    break
            if gecko_path:
                service = FirefoxService(executable_path=gecko_path)
                driver = webdriver.Firefox(service=service, options=options)
            else:
                driver = webdriver.Firefox(options=options)
            
        driver.set_page_load_timeout(60)
        
        try:
            # Domain must be loaded before adding cookies
            driver.get("https://www.instagram.com/")
            time.sleep(5)
            
            # Try to inject cookies from Instaloader session first (portable)
            if self._inject_cookies_from_instaloader(driver):
                self.logger.info("Cookies injected from Instaloader session.")
                driver.get("https://www.instagram.com/") # Refresh with cookies
                time.sleep(5)
            
            # Check if we are logged in
            if "login" in driver.current_url or not self._is_logged_in(driver):
                self.logger.warning("Not logged in via Instaloader cookies. Trying Firefox cookiefile fallback...")
                
                if browser == "firefox":
                    cookie_db = self.conf["cookiefile"]
                    if os.path.exists(cookie_db):
                        self.logger.info(f"Injecting cookies from {cookie_db}")
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
                            cookie_dict = {'name': name, 'value': value, 'domain': host, 'path': path}
                            try:
                                driver.add_cookie(cookie_dict)
                            except:
                                pass
                        driver.get("https://www.instagram.com/")
                        time.sleep(5)

                if "login" in driver.current_url or not self._is_logged_in(driver):
                    self.logger.warning("Still not logged in. Attempting manual login.")
                    self._manual_login(driver)
        except Exception as e:
            self.logger.error(f"Error in setup_selenium: {e}")
            
        return driver

    def _inject_cookies_from_instaloader(self, driver):
        try:
            if not self.SESSIONFILE.exists():
                return False
                
            self.logger.info(f"Reading cookies from {self.SESSIONFILE}")
            L = instaloader.Instaloader()
            L.load_session_from_file(self.USER, self.SESSIONFILE)
            
            # instaloader session.cookies is a RequestsCookieJar
            for cookie in L.context._session.cookies:
                cookie_dict = {
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure
                }
                if cookie.expires:
                    cookie_dict['expiry'] = cookie.expires
                
                try:
                    driver.add_cookie(cookie_dict)
                except Exception as e:
                    self.logger.debug(f"Could not add cookie {cookie.name}: {e}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to inject Instaloader cookies: {e}")
            return False

    def _is_logged_in(self, driver):
        # Quick check for logged-in UI elements
        try:
            driver.find_element(By.XPATH, "//*[@aria-label='Home'] | //*[@aria-label='Search'] | //*[@aria-label='New post']")
            return True
        except:
            return False

    def _manual_login(self, driver):
        try:
            self.logger.info("Navigating to login page...")
            driver.get("https://www.instagram.com/accounts/login/")
            wait = WebDriverWait(driver, 20)
            
            # Handle Cookie Consent aggressively
            try:
                self.logger.info("Checking for cookie consent...")
                # Multiple possible cookie buttons
                cookie_selectors = [
                    "//button[contains(text(), 'Allow all cookies')]",
                    "//button[contains(text(), 'Allow essential and optional cookies')]",
                    "//button[contains(text(), 'Accept All')]",
                    "//button[text()='Decline optional cookies']" # Sometimes works better
                ]
                for selector in cookie_selectors:
                    try:
                        cookie_button = driver.find_element(By.XPATH, selector)
                        if cookie_button.is_displayed():
                            cookie_button.click()
                            self.logger.info(f"Dismissed cookie consent with: {selector}")
                            time.sleep(2)
                            break
                    except:
                        continue
            except:
                self.logger.info("Cookie consent logic finished.")

            if "login" not in driver.current_url:
                self.logger.info(f"Already logged in. Current URL: {driver.current_url}")
                return

            self.logger.info(f"Attempting manual login for user: {self.USER}")
            
            # Ensure elements are interactable
            username_selectors = [
                (By.NAME, "username"),
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[name='username']"),
                (By.CSS_SELECTOR, "input[name='email']")
            ]
            
            username_input = None
            for by, selector in username_selectors:
                try:
                    element = wait.until(EC.element_to_be_clickable((by, selector)))
                    self.logger.info(f"Found interactable username field with: {selector}")
                    username_input = element
                    break
                except:
                    continue
            
            if not username_input:
                # If still not clickable, try JS injection as last resort
                self.logger.warning("Username field not clickable via standard methods. Trying fallback...")
                username_input = driver.find_element(By.XPATH, "//input[@name='username'] | //input[@name='email']")
                driver.execute_script("arguments[0].scrollIntoView(true);", username_input)

            password_selectors = [(By.NAME, "password"), (By.NAME, "pass")]
            password_input = None
            for by, selector in password_selectors:
                try:
                    password_input = wait.until(EC.element_to_be_clickable((by, selector)))
                    self.logger.info(f"Found interactable password field with: {selector}")
                    break
                except:
                    continue

            if not password_input:
                self.logger.warning("Password field not clickable via standard methods. Trying fallback...")
                password_input = driver.find_element(By.XPATH, "//input[@name='password'] | //input[@name='pass']")
                driver.execute_script("arguments[0].scrollIntoView(true);", password_input)

            # Clear and type
            driver.execute_script("arguments[0].value = '';", username_input)
            username_input.send_keys(self.USER)
            driver.execute_script("arguments[0].value = '';", password_input)
            password_input.send_keys(self.PASSWORD)
            
            # Click login button
            login_button_selectors = [
                "//div[@role='button' and @aria-label='Log In']",
                "//div[@role='button']//span[text()='Log in']",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//div[@role='button' and contains(text(), 'Log in')]",
            ]
            
            login_button = None
            for selector in login_button_selectors:
                try:
                    # Use presence instead of element_to_be_clickable because it might be aria-disabled
                    login_button = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                    self.logger.info(f"Found login button with: {selector}")
                    break
                except:
                    continue
                    
            if login_button:
                self.logger.info("Attempting to click Log In button...")
                try:
                    # Try JS click immediately as it bypasses aria-disabled and overlaps
                    driver.execute_script("arguments[0].click();", login_button)
                    self.logger.info("JS click successful (presumably)")
                except Exception as click_err:
                    self.logger.warning(f"JS click failed: {click_err}. Trying standard click.")
                    login_button.click()
            else:
                raise Exception("Could not find Log In button")

            self.logger.info("Login button clicked.")
            time.sleep(10)
            
            # Verify login success
            if "login" in driver.current_url:
                self.logger.error("Still on login page after clicking login button.")
                driver.save_screenshot(f"login_fail_page_{int(time.time())}.png")
            else:
                self.logger.info(f"Redirected to: {driver.current_url}")
                # Check for logged-in only elements (like the 'Home' icon or search icon)
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, "//*[@aria-label='Home'] | //*[@aria-label='Search'] | //*[@aria-label='New post']")))
                    self.logger.info("Login verified via presence of nav elements.")
                except:
                    self.logger.warning("Could not verify login via nav elements, but not on login page.")
            
            self._dismiss_popups(driver)

        except Exception as e:
            self.logger.error(f"Manual login failed: {e}")
            driver.save_screenshot(f"login_exception_{int(time.time())}.png")

    def _dismiss_popups(self, driver):
        self.logger.info("Checking for popups to dismiss...")
        wait = WebDriverWait(driver, 5)
        # List of button texts or aria-labels that indicate a 'Not Now' or close action
        dismiss_selectors = [
            "//button[text()='Not Now']",
            "//button[text()='Not now']",
            "//div[@role='button' and text()='Not now']",
            "//div[@role='button' and text()='Not Now']",
            "//*[@aria-label='Close']",
            "//svg[@aria-label='Close']/ancestor::div[@role='button']"
        ]
        for selector in dismiss_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for el in elements:
                    if el.is_displayed():
                        el.click()
                        self.logger.info(f"Dismissed popup element: {selector}")
                        time.sleep(1)
            except:
                continue

    @staticmethod
    def teardown(driver):
        if driver:
            driver.quit()

    def setup_instaloader(self):
        # Monkey-patch os.utime to ignore PermissionError (common on some LXC mounts)
        original_utime = os.utime
        def patched_utime(path, times=None, **kwargs):
            try:
                return original_utime(path, times, **kwargs)
            except PermissionError:
                self.logger.warning(f"PermissionError ignored for os.utime on {path}")
                return None
        os.utime = patched_utime

        L = instaloader.Instaloader(dirname_pattern=self.conf["tmpdir"])
        
        # If USER is None, we need to find it from the session file or config
        if not self.USER:
            self.logger.warning("USER environment variable is None. Trying to extract from session file...")
            # Extract username from 'session-USERNAME' filename pattern
            if self.SESSIONFILE:
                filename = self.SESSIONFILE.name
                if filename.startswith("session-"):
                    self.USER = filename.replace("session-", "")
                    self.logger.info(f"Extracted USER from filename: {self.USER}")

        if not self.USER:
            self.logger.error("Instagram USER not found in environment or session filename.")
            # We can still try to refresh if Selenium is available later, 
            # but for now we try a blind load if the file exists
            try:
                # Instaloader.load_session_from_file(None, ...) doesn't work well
                pass
            except:
                pass

        try:
            if self.USER and self.SESSIONFILE.exists():
                L.load_session_from_file(self.USER, self.SESSIONFILE)
                testLogin = L.test_login()
                self.logger.info(f"testLogin: {testLogin}")
                if testLogin:
                    return L
        except Exception as e:
            self.logger.warning(f"Failed to load session file {self.SESSIONFILE}: {e}")

        self.logger.info("Session invalid or missing. Attempting to refresh via Selenium cookies...")
        if self.instaloader_import_session():
             # After import, USER should definitely be set (from test_login)
             L.load_session_from_file(self.USER, self.SESSIONFILE)
             return L
        else:
             raise typer.Exit("Instaloader login failed.")

    def _is_working_offline(self):
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        return len(files) > 0

    def instaloader_process_downloaded(self) -> list[str]:
        files = glob.glob("*xz", root_dir=self.conf["tmpdir"])
        urls = []
        for file in files:
            tmpdir = self.conf["tmpdir"]
            jsonPost = lzma.open(f"{tmpdir}/{file}").read().decode("utf-8")
            json_obj = json.loads(jsonPost)
            df1 = pd.json_normalize(json_obj).reset_index(drop=True)
            df1.insert(loc=0, column="ingest_timestamp", value=now_ts)
            df1.insert(loc=0, column="src_file", value=file)
            table_name = "instagram_raw_2"
            df1 = df1.astype(str).replace("nan", np.nan)
            
            if not self.ProcessingUtils._table_exists(table_name=table_name):
                self._db_handler.df_to_db(df=df1, table_name=table_name)
            else:
                cols_in_db = self._db_handler.fields_in_table(table_name)
                df1_cols = sorted(set(df1.columns))
                if set(df1.columns) != set(cols_in_db):
                    new_columns = [key for key in df1_cols if key not in cols_in_db]
                    for new_col in new_columns:
                        self._db_handler.alter_table(table_name=table_name, new_col=new_col)
                    cols_in_db = self._db_handler.fields_in_table(table_name)
                
                placeholders = ", ".join(["?" for _ in cols_in_db])
                quoted_columns = ", ".join([f'"{col}"' for col in cols_in_db])
                values = [df1[col].iloc[0] if col in df1_cols else np.nan for col in cols_in_db]
                self._db_handler.row_to_raw_instagram(
                    table_name=table_name,
                    placeholders=placeholders,
                    quoted_columns=quoted_columns,
                    values=values,
                )
            
            # Analyze the txt file if it exists
            try:
                from logme.processors.InstagramProcessor import InstagramProcessor
                processor = InstagramProcessor()
                txt_file = file.replace(".json.xz", ".txt")
                txt_path = os.path.join(self.conf["tmpdir"], txt_file)
                processor.process_txt_file(txt_path)
            except Exception as e:
                self.logger.error(f"Error in InstagramProcessor: {e}")

            post_url = f'https://www.instagram.com/p/{df1["node.shortcode"].iloc[0]}/'
            urls.append(post_url)
        return urls

    def instaloader_process(self, instaloader_session, driver_session):
        try:
            self.logger.info("Attempting to download saved posts...")
            instaloader_session.download_saved_posts(1)
        except PermissionError as pe:
            # Specific handling for PermissionError (e.g. os.utime on restricted mounts)
            self.logger.error(f"Filesystem permission error (likely external HDD mount): {pe}. Check mount options.")
            # We don't refresh session here as it's not a login issue
        except (instaloader.LoginRequiredException, instaloader.ConnectionException, Exception) as e:
            self.logger.warning(f"Instaloader session issue or error: {e}. Attempting refresh from Selenium...")
            if self.instaloader_import_session(driver=driver_session):
                self.logger.info(f"Session refreshed for {self.USER}. Reloading and retrying download...")
                instaloader_session.load_session_from_file(self.USER, self.SESSIONFILE)
                instaloader_session.download_saved_posts(1)
            else:
                self.logger.error("Failed to refresh Instaloader session from Selenium.")
                raise
            
        urls = self.instaloader_process_downloaded()
        self.move_to_exteranl_hdd()
        return self.unsave(urls, driver_session)

    def move_to_exteranl_hdd(self):
        file_names = os.listdir(self.conf["tmpdir"])
        for file_name in file_names:
            if not os.path.exists(os.path.join(self.conf["external_hdd"], file_name)):
                shutil.move(os.path.join(self.conf["tmpdir"], file_name),
                           os.path.join(self.conf["external_hdd"], file_name))
            else:
                os.remove(os.path.join(self.conf["tmpdir"], file_name))

    def unsave(self, urls, driver):
        next = False
        wait = WebDriverWait(driver, 15)
        for url in urls:
            self.logger.info(f"Unsaving: {url}")
            driver.get(url)
            
            # Mandatory screenshot for debugging
            time.sleep(5)
            screenshot_path = f"unsave_debug_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            self.logger.info(f"Saved screenshot to {screenshot_path}. URL: {driver.current_url}")

            if "accounts/login" in driver.current_url:
                self.logger.warning("Redirected to login page. Attempting re-login...")
                self._manual_login(driver)
                driver.get(url)
                time.sleep(5)
            
            # Dismiss any blocking popups (like the 'Never miss a post' signup modal)
            self._dismiss_popups(driver)

            try:
                # 1. Wait specifically for 'Remove' label as we know it exists in the post
                self.logger.info("Waiting for 'Remove' button...")
                found = False
                try:
                    remove_element = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@aria-label='Remove']")))
                    # Find the clickable container
                    try:
                        clickable = remove_element.find_element(By.XPATH, "./ancestor::div[@role='button'] | ./ancestor::button")
                    except:
                        clickable = remove_element
                    
                    driver.execute_script("arguments[0].scrollIntoView(true);", clickable)
                    time.sleep(1)
                    try:
                        clickable.click()
                    except:
                        driver.execute_script("arguments[0].click();", clickable)
                        
                    self.logger.info("Successfully clicked 'Remove' button.")
                    found = True
                except Exception as wait_err:
                    self.logger.warning(f"'Remove' button not found via wait: {wait_err}")

                # 2. Fallback to other selectors if direct wait failed
                if not found:
                    selectors = [
                        "//div[@role='button']//svg[@aria-label='Remove']",
                        "//div[contains(@class, 'x1i10hfl')]//svg[@aria-label='Remove']",
                        "//*[@aria-label='Unsave']",
                    ]
                    for selector in selectors:
                        try:
                            elements = driver.find_elements(By.XPATH, selector)
                            if elements:
                                clickable = elements[0]
                                try:
                                    clickable = clickable.find_element(By.XPATH, "./ancestor::div[@role='button'] | ./ancestor::button")
                                except:
                                    pass
                                driver.execute_script("arguments[0].click();", clickable)
                                self.logger.info(f"Clicked remove/unsave via fallback: {selector}")
                                found = True
                                break
                        except:
                            continue
                
                # 3. Last resort: click 'Save' button only if we are absolutely sure we can't find 'Remove'
                if not found:
                    self.logger.info("Could not find 'Remove'. Checking if already unsaved (shows 'Save')...")
                    try:
                        save_element = driver.find_element(By.XPATH, "//*[@aria-label='Save']")
                        self.logger.info("Found 'Save' button, post might already be unsaved.")
                        found = True # Treat as success if it is already in the target state
                    except:
                        self.logger.warning(f"Could not find any save/unsave button for {url}.")

                if found:
                    next = True
                    time.sleep(3)
                    driver.save_screenshot(f"unsave_final_{int(time.time())}.png")
            except Exception as e:
                self.logger.error(f"Error during unsave for {url}: {e}")
                next = False
        return next
