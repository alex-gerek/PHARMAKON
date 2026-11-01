import os
import sys
import time
import urllib.request
import subprocess
import threading
import webbrowser
from pathlib import Path

# Setup paths for standard and frozen environments
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(sys.executable).resolve().parent))
    PROJECT_DIR = Path(sys.executable).resolve().parent
    sys.path.insert(0, str(PROJECT_DIR))
    sys.path.insert(0, str(BASE_DIR))
else:
    PROJECT_DIR = Path(__file__).resolve().parent
    BASE_DIR = PROJECT_DIR
    sys.path.insert(0, str(PROJECT_DIR))

SERVER_SCRIPT = str(PROJECT_DIR / "gui" / "server.py")
ICON_PATH = str(PROJECT_DIR / "pharmakon_hd_256.ico")
URL = "http://127.0.0.1:7860"

def is_server_running():
    try:
        with urllib.request.urlopen(f"{URL}/api/system-info", timeout=1) as res:
            return res.getcode() == 200
    except Exception:
        return False

def stop_server():
    try:
        req = urllib.request.Request(f"{URL}/api/shutdown", method="POST")
        with urllib.request.urlopen(req, timeout=2) as res:
            return res.getcode() == 200
    except Exception:
        return False

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
            return subprocess.Popen([cp, f"--app={URL}", "--window-size=1360,920"])

    # Fallback to Edge App Mode
    for ep in edge_paths:
        if os.path.exists(ep):
            return subprocess.Popen([ep, f"--app={URL}", "--window-size=1360,920"])

    # Fallback to default browser
    webbrowser.open(URL)
    return None

def start_server_dev():
    if is_server_running():
        return
    py_exe = sys.executable
    if py_exe.endswith("pythonw.exe"):
        py_exe = py_exe.replace("pythonw.exe", "python.exe")
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen([py_exe, SERVER_SCRIPT], cwd=str(PROJECT_DIR), creationflags=creation_flags)
    else:
        subprocess.Popen([py_exe, SERVER_SCRIPT], cwd=str(PROJECT_DIR))

    for _ in range(30):
        time.sleep(0.2)
        if is_server_running():
            break

def main():
    if "--stop" in sys.argv:
        if stop_server():
            print("PHARMAKON Studio Server stopped.")
        else:
            print("PHARMAKON Server is not currently running.")
        return

    # If already running, just open UI
    if is_server_running():
        open_ui()
        return

    if getattr(sys, 'frozen', False):
        import uvicorn
        from gui.server import app

        if "--server-only" in sys.argv:
            uvicorn.run(app, host="127.0.0.1", port=7860, log_level="info")
            return

        # Start server in thread
        server_thread = threading.Thread(
            target=lambda: uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning"),
            daemon=True
        )
        server_thread.start()

        # Wait for server ready
        for _ in range(50):
            time.sleep(0.1)
            if is_server_running():
                break

        # Open UI
        ui_proc = open_ui()

        if ui_proc:
            ui_proc.wait()
        else:
            try:
                while True:
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                pass
    else:
        start_server_dev()
        open_ui()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
