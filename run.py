#!/usr/bin/env python3
"""Cross-platform launcher for the Rhythm Detector GUI.

Creates (or reuses) a local virtual environment, installs the project's
dependencies into it, and starts the GUI. Works identically on Windows,
macOS and Linux -- the only prerequisite is a system Python (>= 3.10) that
includes the Tk bindings (see the hints printed below if Tk is missing).

Usage:
    python run.py                 # set up the venv and launch the GUI
    python run.py --recreate      # rebuild the virtual environment first
    python run.py --skip-install  # launch without touching dependencies
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
IMPL_DIR = REPO_ROOT / "code" / "python_implementation"
GUI_ENTRY = IMPL_DIR / "GUI" / "rhythm_detector_gui.py"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
VENV_DIR = REPO_ROOT / ".venv"
MIN_PYTHON = (3, 10)


# --- small ASCII-only logging helpers (avoid unicode/ANSI for Windows consoles) ---
def info(msg: str) -> None:
    print(f"[ run.py ] {msg}")


def warn(msg: str) -> None:
    print(f"[ warn  ] {msg}")


def error(msg: str) -> None:
    print(f"[ error ] {msg}", file=sys.stderr)


def venv_python(venv_dir: Path) -> Path:
    """Return the path to the Python executable inside a virtual environment."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        error(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required, "
            f"but this is {platform.python_version()}."
        )
        sys.exit(1)
    info(f"Using {platform.python_implementation()} {platform.python_version()} on {platform.system()}")


def tkinter_install_hint() -> str:
    """Best-effort, platform-specific instructions for installing Tk."""
    system = platform.system()
    if system == "Windows":
        return ("Reinstall Python from python.org and keep the "
                "'tcl/tk and IDLE' feature enabled.")
    if system == "Darwin":
        return ("Install a Tk-enabled Python, e.g. 'brew install python-tk' "
                "or use the python.org installer.")
    # Linux: look at the distro id to pick the right package manager.
    distro = ""
    os_release = Path("/etc/os-release")
    if os_release.is_file():
        fields = {}
        for line in os_release.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                fields[key] = value.strip().strip('"')
        distro = f"{fields.get('ID', '')} {fields.get('ID_LIKE', '')}".lower()

    if any(d in distro for d in ("debian", "ubuntu")):
        return "sudo apt install python3-tk"
    if any(d in distro for d in ("fedora", "rhel", "centos")):
        return "sudo dnf install python3-tkinter"
    if "arch" in distro:
        return "sudo pacman -S tk"
    if any(d in distro for d in ("suse", "opensuse")):
        return "sudo zypper install python3-tk"
    return "Install your distribution's Tk package for Python (e.g. python3-tk / python3-tkinter)."


def check_tkinter(python_exe: Path) -> None:
    """Abort with platform-specific install advice if the venv has no Tk bindings."""
    result = subprocess.run(
        [str(python_exe), "-c", "import tkinter"],
        capture_output=True,
        text=True,
        check=False,  # a non-zero exit IS the signal we are testing for
    )
    if result.returncode != 0:
        error("Tkinter is not available for this Python installation.")
        error("The GUI cannot start without it. To fix:")
        error(f"    {tkinter_install_hint()}")
        sys.exit(1)
    info("Tkinter is available")


def ensure_venv(recreate: bool) -> Path:
    """Create or reuse the local venv, returning the path to its interpreter."""
    if recreate and VENV_DIR.exists():
        info("Removing existing virtual environment...")
        shutil.rmtree(VENV_DIR)

    if not VENV_DIR.exists():
        info(f"Creating virtual environment at {VENV_DIR}")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        info("Reusing existing virtual environment")

    py = venv_python(VENV_DIR)
    if not py.exists():
        error(f"Virtual environment looks broken: {py} not found. "
              f"Try: python run.py --recreate")
        sys.exit(1)
    return py


def install_deps(python_exe: Path) -> None:
    if not REQUIREMENTS.is_file():
        error(f"requirements.txt not found at {REQUIREMENTS}")
        sys.exit(1)
    info("Upgrading pip...")
    subprocess.check_call([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    info("Installing dependencies (this may take a minute)...")
    subprocess.check_call([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    info("Dependencies installed")


def launch_gui(python_exe: Path) -> int:
    if not GUI_ENTRY.is_file():
        error(f"GUI entry point not found at {GUI_ENTRY}")
        sys.exit(1)
    info("Starting Rhythm Detector GUI...")
    # Run from the implementation directory so the GUI's sibling imports resolve,
    # matching how the application expects to be launched.
    return subprocess.call([str(python_exe), str(GUI_ENTRY)], cwd=str(IMPL_DIR))


def main() -> int:
    """Parse arguments, prepare the environment and launch the GUI."""
    parser = argparse.ArgumentParser(description="Launch the Rhythm Detector GUI.")
    parser.add_argument("--recreate", action="store_true",
                        help="Delete and rebuild the virtual environment.")
    parser.add_argument("--skip-install", action="store_true",
                        help="Skip dependency installation and launch directly.")
    args = parser.parse_args()

    check_python_version()
    python_exe = ensure_venv(recreate=args.recreate)
    if not args.skip_install:
        install_deps(python_exe)
    check_tkinter(python_exe)
    return launch_gui(python_exe)


if __name__ == "__main__":
    raise SystemExit(main())
