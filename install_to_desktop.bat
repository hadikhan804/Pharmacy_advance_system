@echo off
setlocal
set "DEST=%USERPROFILE%\Desktop\HadiPharmacy"
set "ZIP=%~dp0HadiPharmacy.zip"
if not exist "%ZIP%" goto FAIL
mkdir "%USERPROFILE%\Desktop" 2>nul
tar -xf "%ZIP%" -C "%USERPROFILE%\Desktop"
if not exist "%DEST%\HadiPharmacy.exe" goto FAIL
if not exist "%DEST%\_internal\python312.dll" goto FAIL
start "" "%DEST%\HadiPharmacy.exe"
exit /b 0
:FAIL
mshta "javascript:alert('Install failed. Extract HadiPharmacy.zip to the Desktop, then open the folder and run HadiPharmacy.exe');close()"
exit /b 1
