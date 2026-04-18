
import subprocess
import time
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

def test_remote_style():
    print("--- Starting Geckodriver Manually ---")
    port = 4444
    # We use the method that worked in debug_env.py
    log_file = open("standalone_gecko.log", "w")
    gecko_process = subprocess.Popen(
        ["/usr/local/bin/geckodriver", "--port", str(port), "--host", "127.0.0.1", "--log", "trace"],
        stdout=log_file,
        stderr=subprocess.STDOUT
    )
    
    print(f"Geckodriver started (PID: {gecko_process.pid})")
    time.sleep(2) # Wait for it to bind
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    
    try:
        print(f"Connecting Selenium to 127.0.0.1:{port}...")
        # In Selenium 4, we use the remote connection for a standalone driver
        driver = webdriver.Remote(
            command_executor=f'http://127.0.0.1:{port}',
            options=options
        )
        
        print("SUCCESS: Selenium connected to standalone Geckodriver!")
        driver.get("https://www.google.com")
        print(f"Title: {driver.title}")
        driver.quit()
        
    except Exception as e:
        print(f"FAILURE: {e}")
        print("\n--- STANDALONE GECKO LOG ---")
        log_file.flush()
        with open("standalone_gecko.log", "r") as f:
            print(f.read())
    finally:
        gecko_process.terminate()

if __name__ == "__main__":
    test_remote_style()
