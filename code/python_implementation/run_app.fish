#!/usr/bin/env fish

# Rhythm Detector Application Launcher (Fish Shell Version)
# This script creates a virtual environment, installs dependencies, and runs the GUI

# Colors for output
set RED '\033[0;31m'
set GREEN '\033[0;32m'
set YELLOW '\033[1;33m'
set BLUE '\033[0;34m'
set NC '\033[0m' # No Color

# Get the directory where this script is located
set SCRIPT_DIR (dirname (status --current-filename))
cd $SCRIPT_DIR

echo -e "$BLUE========================================$NC"
echo -e "$BLUE  Rhythm Detector Application Launcher$NC"
echo -e "$BLUE========================================$NC\n"

# Check if Python 3 is installed
if not command -v python3 &> /dev/null
    echo -e "$RED""Error: Python 3 is not installed.$NC"
    echo "Please install Python 3 and try again."
    exit 1
end

set PYTHON_VERSION (python3 --version)
echo -e "$GREEN✓$NC Found $PYTHON_VERSION"

# Check if python3-tkinter is installed
if not python3 -c "import tkinter" 2>/dev/null
    echo -e "$YELLOW""Warning: python3-tkinter is not installed.$NC"
    echo "Install it with: sudo dnf install python3-tkinter"
    exit 1
end
echo -e "$GREEN✓$NC Tkinter is available"

# Virtual environment setup
set VENV_DIR "venv"

if test -d $VENV_DIR
    echo -e "$YELLOW""Virtual environment already exists.$NC"
    read -l -P "Do you want to recreate it? (y/N): " response
    if test "$response" = "y" -o "$response" = "Y"
        echo -e "$YELLOW""Removing existing virtual environment...$NC"
        rm -rf $VENV_DIR
    else
        echo -e "$GREEN""Using existing virtual environment.$NC"
    end
end

# Create virtual environment if it doesn't exist
if not test -d $VENV_DIR
    echo -e "$BLUE""Creating virtual environment...$NC"
    python3 -m venv $VENV_DIR
    echo -e "$GREEN✓$NC Virtual environment created"
else
    echo -e "$GREEN✓$NC Virtual environment found"
end

# Activate virtual environment (fish syntax)
echo -e "$BLUE""Activating virtual environment...$NC"
source $VENV_DIR/bin/activate.fish
echo -e "$GREEN✓$NC Virtual environment activated"

# Upgrade pip
echo -e "$BLUE""Upgrading pip...$NC"
pip install --upgrade pip --quiet
echo -e "$GREEN✓$NC pip upgraded"

# Check if requirements.txt exists
if not test -f "requirements.txt"
    echo -e "$RED""Error: requirements.txt not found in $SCRIPT_DIR$NC"
    echo "Please create requirements.txt first."
    deactivate
    exit 1
end

# Install/upgrade dependencies
echo -e "$BLUE""Installing dependencies from requirements.txt...$NC"
pip install -r requirements.txt
echo -e "$GREEN✓$NC Dependencies installed"

# Verify critical imports
echo -e "$BLUE""Verifying installation...$NC"
python3 -c '
import sys
errors = []

try:
    import numpy
    print("  ✓ numpy")
except ImportError as e:
    errors.append("numpy")
    print(f"  ✗ numpy: {e}")

try:
    import scipy
    print("  ✓ scipy")
except ImportError as e:
    errors.append("scipy")
    print(f"  ✗ scipy: {e}")

try:
    import matplotlib
    print("  ✓ matplotlib")
except ImportError as e:
    errors.append("matplotlib")
    print(f"  ✗ matplotlib: {e}")

try:
    from PIL import Image, ImageTk
    print("  ✓ PIL/ImageTk")
except ImportError as e:
    errors.append("PIL/ImageTk")
    print(f"  ✗ PIL/ImageTk: {e}")

try:
    import soundfile
    print("  ✓ soundfile")
except ImportError as e:
    errors.append("soundfile")
    print(f"  ✗ soundfile: {e}")

try:
    import audioread
    print("  ✓ audioread")
except ImportError as e:
    errors.append("audioread")
    print(f"  ✗ audioread: {e}")

if errors:
    print(f"\nERROR: Failed to import: {', '.join(errors)}")
    sys.exit(1)
'

if test $status -ne 0
    echo -e "$RED✗ Installation verification failed$NC"
    deactivate
    exit 1
end
echo -e "$GREEN✓$NC All dependencies verified"

# Run the application
echo -e "\n$BLUE========================================$NC"
echo -e "$GREEN""Starting Rhythm Detector GUI...$NC"
echo -e "$BLUE========================================$NC\n"

# Run the GUI (using the main entry point)
python3 GUI/rhythm_detector_gui.py

# Capture exit code
set EXIT_CODE $status

# Deactivate virtual environment on exit
deactivate

if test $EXIT_CODE -eq 0
    echo -e "\n$GREEN""Application closed successfully.$NC"
else
    echo -e "\n$RED""Application exited with error code: $EXIT_CODE$NC"
end

exit $EXIT_CODE