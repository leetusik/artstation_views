@echo off
SETLOCAL

echo Starting ArtStation View Booster...

:: Check if Python is installed
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Python is not installed. Please install Python first.
    exit /b 1
)

:: Check if uv is installed
uv --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Installing uv package manager...
    powershell -Command "& {Invoke-WebRequest -UseBasicParsing https://astral.sh/uv/install.ps1 | powershell -Command -}"
    
    :: Refresh the PATH environment variable
    call RefreshEnv.cmd >nul 2>&1
    IF %ERRORLEVEL% NEQ 0 (
        echo Please restart this script after installation.
        pause
        exit /b 0
    )
)

:: Create virtual environment if it doesn't exist
IF NOT EXIST ".venv" (
    echo Creating virtual environment...
    uv venv
)

:: Install dependencies if requirements.txt exists
IF EXIST "requirements.txt" (
    echo Installing dependencies...
    uv pip install -r requirements.txt
) ELSE (
    :: Install playwright if not in requirements
    echo Installing playwright...
    uv pip install playwright
    playwright install chromium
)

:: Run the application
echo Running ArtStation View Booster...
uv run main.py

pause 