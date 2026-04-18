
import logging
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("ReproChrome")

def setup_selenium():
    logger.info("Setting up Chrome with Headless and No-Sandbox...")
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Try to find chromedriver in common paths
    chrome_path = None
    for path in ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver", "/snap/bin/chromedriver"]:
        if os.path.exists(path):
            chrome_path = path
            break
            
    if chrome_path:
        logger.info(f"Using chromedriver at {chrome_path}")
        service = ChromeService(executable_path=chrome_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        logger.info("Chromedriver not found in common paths, relying on system PATH")
        driver = webdriver.Chrome(options=options)
        
    try:
        logger.info("Initializing driver...")
        driver.get("https://www.google.com")
        logger.info(f"Success! Page title: {driver.title}")
        driver.quit()
    except Exception as e:
        logger.error(f"Failed: {e}")

if __name__ == "__main__":
    setup_selenium()
