
import logging
import os
import time
import socket
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Repro")

def setup_selenium():
    logger.info("Setting up Selenium with IPv4 and No-Sandbox...")
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Critical for LXC
    os.environ["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
    
    gecko_path = "/usr/local/bin/geckodriver"
    log_file = os.path.abspath("geckodriver_manual.log")
    
    # Force geckodriver to listen on 127.0.0.1
    service = FirefoxService(
        executable_path=gecko_path,
        log_path=log_file,
        service_args=["--host", "127.0.0.1", "--log", "trace"]
    )
    
    try:
        logger.info("Initializing driver...")
        # We manually set the command executor to 127.0.0.1 to avoid localhost resolution issues
        driver = webdriver.Firefox(service=service, options=options)
        
        logger.info("Success! Driver initialized.")
        driver.get("https://www.google.com")
        logger.info(f"Page title: {driver.title}")
        driver.quit()
    except Exception as e:
        logger.error(f"Failed: {e}")
        if os.path.exists(log_file):
            print("\n--- GECKODRIVER LOG ---")
            with open(log_file, "r") as f:
                print(f.read())
        else:
            logger.error("Log file was still not created. This points to a OS-level block on geckodriver execution.")

if __name__ == "__main__":
    setup_selenium()
