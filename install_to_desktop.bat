@echo off
setlocal
set "DEST=%USERPROFILE%\Desktop\YasirMedicalStore"
set "ZIP=%~dp0YasirMedicalStore.zip"
if not exist "%ZIP%" goto FAIL
mkdir "%USERPROFILE%\Desktop" 2>nul
tar -xf "%ZIP%" -C "%USERPROFILE%\Desktop"
if not exist "%DEST%\YasirMedicalStore.exe" goto FAIL
if not exist "%DEST%\_internal\python312.dll" goto FAIL
start "" "%DEST%\YasirMedicalStore.exe"
exit /b 0
:FAIL
mshta "javascript:alert('Install failed. Extract YasirMedicalStore.zip to the Desktop, then open the folder and run YasirMedicalStore.exe');close()"
exit /b 1
