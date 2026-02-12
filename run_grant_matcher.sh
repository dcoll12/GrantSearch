#!/bin/bash
# ============================================
# Instrumentl Grant Matcher - Mac/Linux Launcher
# ============================================
#
# Double-click this file or run from terminal to start!
#

echo ""
echo "============================================"
echo "   Instrumentl Grant Matcher"
echo "============================================"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo ""
    echo "Please install Python from https://www.python.org/downloads/"
    echo "Or on Mac: brew install python3"
    echo "Or on Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-tk"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if tkinter is available
python3 -c "import tkinter" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: tkinter is not installed"
    echo ""
    echo "On Ubuntu/Debian: sudo apt-get install python3-tk"
    echo "On Mac: Python from python.org includes tkinter"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if this is first run (requirements not installed)
if [ ! -f ".installed" ]; then
    echo "First run detected - Installing dependencies..."
    echo "This may take a few minutes..."
    echo ""
    
    pip3 install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "ERROR: Failed to install dependencies"
        echo "Please try running: pip3 install -r requirements.txt"
        read -p "Press Enter to exit..."
        exit 1
    fi
    
    touch .installed
    echo "Dependencies installed successfully!"
    echo ""
fi

# Run the application
echo "Starting Grant Matcher..."
python3 grant_matcher.py

if [ $? -ne 0 ]; then
    echo ""
    echo "The application encountered an error."
    read -p "Press Enter to exit..."
fi
