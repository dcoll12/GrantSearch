@echo off
REM ============================================
REM Instrumentl Grant Matcher - Windows Launcher
REM ============================================
REM 
REM Double-click this file to run the application!
REM 

echo.
echo ============================================
echo    Instrumentl Grant Matcher
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

REM Check if this is first run (requirements not installed)
if not exist ".installed" (
    echo First run detected - Installing dependencies...
    echo This may take a few minutes...
    echo.
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        echo Please try running: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo. > .installed
    echo Dependencies installed successfully!
    echo.
)

REM Run the application
echo Starting Grant Matcher...
python grant_matcher.py

if errorlevel 1 (
    echo.
    echo The application encountered an error.
    pause
)
