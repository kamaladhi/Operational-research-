@echo off
rem ---------------------------------------------------------------------------
rem  Nurse Rostering OR project - one-click launcher (Windows)
rem  First run: creates a local virtual environment (.venv) and installs requirements.txt
rem  Afterwards: just starts the Streamlit app (http://localhost:8501)
rem ---------------------------------------------------------------------------
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment ...
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment. Is Python 3.10+ installed and on PATH?
        pause
        exit /b 1
    )
    echo Installing requirements ...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Installing the requirements failed. Check your internet connection.
        pause
        exit /b 1
    )
)

echo Starting the application ...
".venv\Scripts\python.exe" -m streamlit run app.py
pause
