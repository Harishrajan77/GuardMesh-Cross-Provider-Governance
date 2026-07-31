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

def start_backend():
    print("[+] Starting FastAPI Gateway on http://127.0.0.1:8000...")
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"]
    )

def start_frontend():
    print("[+] Starting Streamlit Dashboard on http://localhost:8501...")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"]
    )

def main():
    print("=" * 60)
    print(" GuardMesh Enterprise Unified Launcher")
    print("=" * 60)

    # Automatically release ports 8000 and 8501 if previously occupied
    print("[1/3] Releasing network ports 8000 and 8501...")
    free_port(8000)
    free_port(8501)
    time.sleep(1)
    
    # Start processes
    backend = start_backend()
    time.sleep(3)
    frontend = start_frontend()
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
            # Auto-restart backend if terminated unexpectedly
            if backend.poll() is not None:
                print(f"[RECOVERY] Backend exited with code {backend.poll()}. Restarting backend...")
                free_port(8000)
                time.sleep(1)
                backend = start_backend()
            # Auto-restart frontend if terminated unexpectedly
            if frontend.poll() is not None:
                print(f"[RECOVERY] Frontend exited with code {frontend.poll()}. Restarting frontend...")
                free_port(8501)
                time.sleep(1)
                frontend = start_frontend()
            time.sleep(2)
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
