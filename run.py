import subprocess
import sys
import time
import os
import webbrowser

def free_port(port: int):
    """Free port if occupied using native Windows taskkill and netstat."""
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
    print("=" * 60)
    print(" GuardMesh Enterprise Unified Launcher")
    print("=" * 60)

    # Automatically release ports 8000 and 8501 if previously occupied
    print("[1/3] Releasing network ports 8000 and 8501...")
    free_port(8000)
    free_port(8501)
    time.sleep(1)
    
    # Start the backend API server
    print("[2/3] Starting FastAPI Gateway on http://127.0.0.1:8000...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"]
    )
    
    # Wait for backend initialization
    time.sleep(3)
    
    # Start the Streamlit dashboard
    print("[3/3] Starting Streamlit Dashboard on http://localhost:8501...")
    frontend = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"]
    )
    
    time.sleep(2)
    print("\n" + "=" * 60)
    print(" [SUCCESS] GuardMesh Gateway & Dashboard are active!")
    print("  - Backend Gateway API:  http://127.0.0.1:8000")
    print("  - Swagger API Docs:     http://127.0.0.1:8000/docs")
    print("  - Streamlit Dashboard:  http://localhost:8501")
    print(" >>> Press Ctrl+C in this terminal to stop all services. <<<")
    print("=" * 60 + "\n")
    
    # Automatically open browser
    try:
        webbrowser.open("http://localhost:8501")
    except Exception:
        pass
    
    try:
        while True:
            # Check if either process exited unexpectedly
            if backend.poll() is not None:
                print(f"[ALERT] Backend exited with code: {backend.poll()}")
                break
            if frontend.poll() is not None:
                print(f"[ALERT] Frontend exited with code: {frontend.poll()}")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping GuardMesh services...")
    finally:
        # Terminate both subprocesses gracefully
        backend.terminate()
        frontend.terminate()
        backend.wait()
        frontend.wait()
        print("[FINISHED] All GuardMesh services stopped cleanly.")

if __name__ == "__main__":
    main()
