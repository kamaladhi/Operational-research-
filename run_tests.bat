@echo off
rem  Runs the automated test-suite.
rem    run_tests.bat          -> fast suite (about 1 minute)
rem    run_tests.bat slow     -> also solves Instances 3 and 4 live (about 6 minutes)
cd /d "%~dp0"
if "%1"=="slow" set RUN_SLOW_TESTS=1
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -W ignore -m unittest discover -s tests -t . -v
) else (
    python -W ignore -m unittest discover -s tests -t . -v
)
pause
