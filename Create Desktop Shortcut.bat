@echo off
cd /d "%~dp0"
set "TARGET=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%TARGET%" set "TARGET=%~dp0.venv\Scripts\python.exe"
if not exist "%TARGET%" (
  echo Virtual environment not found.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Yasir Medical Store.lnk'));" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.Arguments = '\"%~dp0run.py\"';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.WindowStyle = 1;" ^
  "$s.Description = 'Yasir Medical Store — Pharmacy POS';" ^
  "$s.Save();" ^
  "Write-Host 'Shortcut created on your Desktop.'"
pause
