import os
import sys
import time
import urllib.request
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(PROJECT_DIR, "gui", "server.py")
ICON_PATH = os.path.join(PROJECT_DIR, "pharmakon_hd_256.ico")
URL = "http://127.0.0.1:7860"

def is_server_running():
    try:
        with urllib.request.urlopen(f"{URL}/api/system-info", timeout=1) as res:
            return res.getcode() == 200
    except Exception:
        return False

def start_server():
    if is_server_running():
        return
    py_exe = sys.executable
    if py_exe.endswith("pythonw.exe"):
        py_exe = py_exe.replace("pythonw.exe", "python.exe")
    # Launch server as detached background process
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen([py_exe, SERVER_SCRIPT], cwd=PROJECT_DIR, creationflags=creation_flags)
    else:
        subprocess.Popen([py_exe, SERVER_SCRIPT], cwd=PROJECT_DIR)

    # Wait up to 5 seconds for server to be responsive
    for _ in range(25):
        time.sleep(0.2)
        if is_server_running():
            break

def open_ui():
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]

    # Prioritize Chrome App Mode
    for cp in chrome_paths:
        if os.path.exists(cp):
            subprocess.Popen([cp, f"--app={URL}", "--window-size=1360,920"])
            return

    # Fallback to Edge App Mode
    for ep in edge_paths:
        if os.path.exists(ep):
            subprocess.Popen([ep, f"--app={URL}", "--window-size=1360,920"])
            return

    # Fallback to default browser
    import webbrowser
    webbrowser.open(URL)

if __name__ == "__main__":
    start_server()
    open_ui()
