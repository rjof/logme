
import subprocess
import socket
import time
import os

def check_binary(name, path):
    print(f"--- Checking {name} ---")
    if not os.path.exists(path):
        print(f"ERROR: {path} does not exist")
        return False
    print(f"Permissions: {oct(os.stat(path).st_mode)}")
    try:
        res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        print(f"Version output: {res.stdout.strip()}")
        return True
    except Exception as e:
        print(f"ERROR running {name}: {e}")
        return False

def test_port_binding():
    print("\n--- Testing Geckodriver Port Binding ---")
    # Start geckodriver manually in the background
    port = 4444
    log_file = "manual_gecko.log"
    process = subprocess.Popen(
        ["/usr/local/bin/geckodriver", "--port", str(port), "--host", "127.0.0.1", "--log", "trace"],
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT
    )
    
    print(f"Started geckodriver (PID: {process.pid}) on port {port}...")
    time.sleep(5) # Give it time to bind
    
    # Check if port is open
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(('127.0.0.1', port))
    
    if result == 0:
        print(f"SUCCESS: Port {port} is open and responding.")
    else:
        print(f"FAILURE: Port {port} is NOT responding (Error code: {result}).")
        if os.path.exists(log_file):
            print("Contents of manual_gecko.log:")
            with open(log_file, "r") as f:
                print(f.read())
    
    process.terminate()

if __name__ == "__main__":
    check_binary("Geckodriver", "/usr/local/bin/geckodriver")
    check_binary("Firefox", "/usr/lib/firefox/firefox")
    
    print("\n--- Environment ---")
    print(f"DISPLAY: {os.environ.get('DISPLAY')}")
    subprocess.run(["df", "-h", "/dev/shm"])
    
    test_port_binding()
