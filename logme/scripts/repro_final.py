
import subprocess
import time
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

def test_final_workaround():
    print("--- Starting Geckodriver with Nuclear Environment ---")
    port = 4444
    log_file = open("standalone_gecko.log", "w")
    
    # Force these at the OS level before starting geckodriver
    env = os.environ.copy()
    env["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
    env["MOZ_NODEJS_SANDBOX"] = "0"
    env["MOZ_DISABLE_GMP_SANDBOX"] = "1"
    env["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"
    env["MOZ_X11_EGL"] = "0" # Disable EGL
    env["MOZ_SOFTWARE_VIDEO"] = "1" # Force software video
    
    gecko_process = subprocess.Popen(
        ["/usr/local/bin/geckodriver", "--port", str(port), "--host", "127.0.0.1", "--log", "trace"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env
    )
    
    print(f"Geckodriver started (PID: {gecko_process.pid})")
    time.sleep(2)
    
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    # Force software rendering via Firefox preferences
    options.set_preference("layers.acceleration.disabled", True)
    options.set_preference("gfx.webrender.all", False)
    options.set_preference("gfx.webrender.software", True)
    
    try:
        print(f"Connecting Selenium to 127.0.0.1:{port}...")
        driver = webdriver.Remote(
            command_executor=f'http://127.0.0.1:{port}',
            options=options
        )
        
        print("SUCCESS: Selenium finally connected!")
        driver.get("https://www.instagram.com")
        print(f"Title: {driver.title}")
        driver.quit()
        
    except Exception as e:
        print(f"FAILURE: {e}")
        print("\n--- STANDALONE GECKO LOG (Check the end) ---")
        log_file.flush()
        with open("standalone_gecko.log", "r") as f:
            lines = f.readlines()
            # Show the last 50 lines where the errors usually are
            print("".join(lines[-50:]))
    finally:
        gecko_process.terminate()

if __name__ == "__main__":
    test_final_workaround()
