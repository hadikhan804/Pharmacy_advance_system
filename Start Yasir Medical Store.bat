@echo off
cd /d "%~dp0"
set "PYW=%~dp0.venv\Scripts\pythonw.exe"
set "PY=%~dp0.venv\Scripts\python.exe"
if exist "%PYW%" (
  start "" "%PYW%" "%~dp0run.py"
) else if exist "%PY%" (
  start "" "%PY%" "%~dp0run.py"
) else (
  echo Python virtual environment not found. Run:  .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
)
