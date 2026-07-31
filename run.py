import os
import sys
import time
import subprocess

# Safely redirect stdin/stdout/stderr for pythonw execution
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
if sys.stdin is None:
    sys.stdin = open(os.devnull, 'r')

import uvicorn
import webbrowser
from app.main import app

def free_port(port: int = 8000):
    """Free port 8000 if occupied using native Windows taskkill."""
    if os.name == 'nt':
        try:
            cmd = f'netstat -ano | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            pids = set()
            for line in output.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and ("LISTENING" in parts[3] or "LISTENING" in line):
                    pid = parts[-1]
                    if pid.isdigit() and pid != '0' and int(pid) != os.getpid():
                        pids.add(pid)
            for pid in pids:
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def main():
    # Release port 8000
    free_port(8000)
    time.sleep(1)

    # Start FastAPI / Uvicorn server directly
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None)

if __name__ == "__main__":
    main()
