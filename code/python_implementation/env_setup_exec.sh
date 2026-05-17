#!/bin/bash

# Rhythm Detector Application Launcher
# This script creates a virtual environment, installs dependencies, and runs the GUI
# Compatible with bash/zsh/sh shells (for fish users, see run_app.fish)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Rhythm Detector Application Launcher${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed.${NC}"
    echo "Please install Python 3 and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} Found $PYTHON_VERSION"

# Check if python3-tkinter is installed (Fedora specific)
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo -e "${YELLOW}Warning: python3-tkinter is not installed.${NC}"
    echo "Install it with: sudo dnf install python3-tkinter"
    exit 1
fi
echo -e "${GREEN}✓${NC} Tkinter is available"

# Virtual environment setup
VENV_DIR="venv"

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment already exists.${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Removing existing virtual environment...${NC}"
        rm -rf "$VENV_DIR"
    else
        echo -e "${GREEN}Using existing virtual environment.${NC}"
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment found"
fi

# Activate virtual environment (bash/zsh compatible)
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}✓${NC} pip upgraded"

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: requirements.txt not found in $SCRIPT_DIR${NC}"
    echo "Please create requirements.txt first."
    deactivate
    exit 1
fi

# Install/upgrade dependencies
echo -e "${BLUE}Installing dependencies from requirements.txt...${NC}"
pip install -r requirements.txt
echo -e "${GREEN}✓${NC} Dependencies installed"

# Verify critical imports
echo -e "${BLUE}Verifying installation...${NC}"
python3 << 'PYEOF'
import sys
errors = []

try:
    import numpy
    print("  ✓ numpy")
except ImportError as e:
    errors.append('numpy')
    print(f"  ✗ numpy: {e}")

try:
    import scipy
    print("  ✓ scipy")
except ImportError as e:
    errors.append('scipy')
    print(f"  ✗ scipy: {e}")

try:
    import matplotlib
    print("  ✓ matplotlib")
except ImportError as e:
    errors.append('matplotlib')
    print(f"  ✗ matplotlib: {e}")

try:
    from PIL import Image, ImageTk
    print("  ✓ PIL/ImageTk")
except ImportError as e:
    errors.append('PIL/ImageTk')
    print(f"  ✗ PIL/ImageTk: {e}")

try:
    import pydub
    print("  ✓ pydub")
except ImportError as e:
    errors.append('pydub')
    print(f"  ✗ pydub: {e}")

if errors:
    print(f'\nERROR: Failed to import: {", ".join(errors)}')
    sys.exit(1)
PYEOF

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Installation verification failed${NC}"
    deactivate
    exit 1
fi
echo -e "${GREEN}✓${NC} All dependencies verified"

# Check for ffmpeg (required by pydub)
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${YELLOW}Warning: ffmpeg is not installed.${NC}"
    echo "pydub requires ffmpeg for audio file processing."
    echo "Install it with: sudo dnf install ffmpeg"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        deactivate
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} ffmpeg is available"
fi

# Run the application
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}Starting Rhythm Detector GUI...${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Run the GUI (using the main entry point)
python3 GUI/rythm_detector_gui.py

# Deactivate virtual environment on exit
EXIT_CODE=$?
deactivate

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}Application closed successfully.${NC}"
else
    echo -e "\n${RED}Application exited with error code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE