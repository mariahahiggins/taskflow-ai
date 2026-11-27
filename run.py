"""Launch the TaskFlow AI backend and frontend."""

import os
# Required for launching and managing local application services.
import subprocess  # nosec B404
import sys
import time
import webbrowser
from pathlib import Path
from http.client import HTTPConnection, HTTPException
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

DATABASE = ROOT / "backend" / "taskflow.db"

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:8501"

ALLOWED_HEALTH_URLS = frozenset({
    f"{BACKEND_URL}/health",
    f"{FRONTEND_URL}/_stcore/health",
})

def get_venv_python(venv, os_name):
    """Return the virtual environment's platform-specific Python path."""
    if os_name == "nt":
        return venv / "Scripts" / "python.exe"

    return venv / "bin" / "python"


VENV_PYTHON = get_venv_python(VENV, os.name)


def wait_for_service(url, process, timeout=30):
    """Wait until an approved local service responds successfully."""
    if url not in ALLOWED_HEALTH_URLS:
        raise ValueError("Unauthorized health-check URL.")

    endpoint = urlsplit(url)
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Service exited during startup.")

        connection = HTTPConnection(
            endpoint.hostname,
            endpoint.port,
            timeout=1,
        )

        try:
            connection.request("GET", endpoint.path)
            response = connection.getresponse()

            if response.status == 200:
                return

        except (OSError, HTTPException):
            pass

        finally:
            connection.close()

        time.sleep(0.5)

    raise RuntimeError(f"Service did not become ready: {url}")


def stop_service(process):
    """Stop a running service."""
    if process is not None and process.poll() is None:
        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run():
    """Start and monitor both application services."""
    if not VENV_PYTHON.exists():
        raise RuntimeError("Run python setup.py first.")

    if not DATABASE.exists():
        raise RuntimeError("Database missing. Run python setup.py first.")

    backend = None
    frontend = None

    try:
        print("Starting FastAPI backend...")

        # Fixed executable and arguments; no user input or shell execution.
        backend = subprocess.Popen( # nosec B603
            [
                str(VENV_PYTHON),
                "-m",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
            shell=False
        )

        wait_for_service(f"{BACKEND_URL}/health", backend)

        print("Starting Streamlit frontend...")

        # Fixed executable and arguments; no user input or shell execution.
        frontend = subprocess.Popen( # nosec B603
            [
                str(VENV_PYTHON),
                "-m",
                "streamlit",
                "run",
                "frontend/app.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ],
            cwd=ROOT,
            shell=False,
            env={
                **os.environ,
                "TASKFLOW_API_URL": BACKEND_URL,
            },
        )

        wait_for_service(
            f"{FRONTEND_URL}/_stcore/health",
            frontend,
        )

        print("\nTaskFlow AI is running!")
        print(f"Application URL: {FRONTEND_URL}")
        print("Press Ctrl+C to stop the application.")

        try:
            if not webbrowser.open(FRONTEND_URL):
                print("Could not automatically open browser.")
        except (webbrowser.Error, OSError):
            print("Could not automatically open browser.")

        while True:
            if backend.poll() is not None:
                raise RuntimeError("Backend stopped unexpectedly.")

            if frontend.poll() is not None:
                raise RuntimeError("Frontend stopped unexpectedly.")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping TaskFlow AI...")

    finally:
        stop_service(frontend)
        stop_service(backend)


def main():
    """Launch the application and return an appropriate exit code."""
    try:
        run()
        return 0

    except (RuntimeError, OSError) as error:
        print(f"Startup failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())