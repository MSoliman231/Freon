@echo off
cd /d "%~dp0"

echo Installing build tools...
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller pillow
if errorlevel 1 goto failed

set EXTRA=
if exist "email_password.txt" (
    set EXTRA=--add-data "email_password.txt;."
    echo The Gmail app password will be packed into the exe.
) else (
    echo WARNING: email_password.txt was not found, so the password emails will not work.
)

echo Building FREON.exe, this takes a few minutes...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name FREON --icon "Assets\icon.png" --add-data "Assets;Assets" %EXTRA% main.py
if errorlevel 1 goto failed

echo.
echo Done. Your program is: dist\FREON.exe
pause
exit /b 0

:failed
echo.
echo Something went wrong. Read the messages above.
pause
exit /b 1