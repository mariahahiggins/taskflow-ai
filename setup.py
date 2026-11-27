"""First-time installation for TaskFlow AI."""

import argparse
import os
import shutil
# Required for executing controlled installation commands.
import subprocess # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"

ENV_FILE = ROOT / "backend" / ".env"
ENV_TEMPLATE = ROOT / "backend" / ".env.example"

def get_venv_python(venv, os_name):
    """Return the virtual environment's platform-specific Python path."""
    if os_name == "nt":
        return venv / "Scripts" / "python.exe"

    return venv / "bin" / "python"


VENV_PYTHON = get_venv_python(VENV, os.name)


def check_python_version():
    """Verify that the supported Python version is installed."""
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            "TaskFlow AI requires Python 3.12. "
            f"Current version: {sys.version.split()[0]}"
        )


def setup(seed=False):
    """Install and configure TaskFlow AI."""
    check_python_version()

    print("Setting up TaskFlow AI...")

    if not VENV_PYTHON.exists():
        print("Creating virtual environment...")
        # Fixed executable and arguments; no user input or shell execution.
        subprocess.run( # nosec B603
            [sys.executable, "-m", "venv", str(VENV)],
            check=True,
            cwd=ROOT,
            shell=False
        )

    print("Installing dependencies...")
    # Fixed executable and arguments; no user input or shell execution.
    subprocess.run( # nosec B603
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
        ],
        check=True,
        cwd=ROOT,
        shell=False
    )

    print("Initializing database...")
    # Fixed executable and arguments; no user input or shell execution.
    subprocess.run( # nosec B603
        [str(VENV_PYTHON), "-m", "backend.init_db"],
        check=True,
        cwd=ROOT,
        shell=False
    )

    if seed:
        print("Loading sample data...")
        # Fixed executable and arguments; no user input or shell execution.
        subprocess.run( # nosec B603
            [str(VENV_PYTHON), "-m", "backend.seed_db"],
            check=True,
            cwd=ROOT,
            shell=False
        )

    if not ENV_FILE.exists():
        print("Creating environment configuration...")
        shutil.copyfile(ENV_TEMPLATE, ENV_FILE)

    print("\nTaskFlow AI setup complete!")
    print("Configure backend/.env to enable AI recommendations.")
    print("Start the application with: python run.py")


def main(argv=None):
    """Process command-line arguments and execute installation."""
    parser = argparse.ArgumentParser(
        description="Install TaskFlow AI."
    )

    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load optional sample employees and tasks.",
    )

    args = parser.parse_args(argv)

    try:
        setup(seed=args.seed)
        return 0

    except subprocess.CalledProcessError:
        print("Setup failed. Review the error above.")
        return 1

    except (RuntimeError, OSError) as error:
        print(f"Setup failed: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())