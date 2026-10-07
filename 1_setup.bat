@echo off
chcp 65001 >nul
title IAJ - First time setup
cd /d "%~dp0"
set PYTHONHOME=
set PYTHONPATH=
set DATABASE_URL=
set PYTHONUTF8=1

echo =====================================================
echo   IAJ website - first time setup on this PC
echo   (PostgreSQL must already be installed)
echo =====================================================
echo.

REM ---------- 1. Python ----------
where python >nul 2>nul || (echo [X] Python is not installed. Install Python 3.12 64-bit from python.org with "Add python.exe to PATH". & pause & exit /b 1)
python -c "import socket, ssl, sqlite3" >nul 2>nul || (echo [X] Python on this PC is broken. Uninstall all Python versions and install Python 3.12 64-bit from python.org. & pause & exit /b 1)

if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe -c "import socket, ssl" >nul 2>nul || rmdir /s /q venv
)
if not exist venv\Scripts\python.exe (
  echo Creating virtual environment...
  python -m venv venv >nul 2>nul
)
if exist venv\Scripts\python.exe (
  venv\Scripts\python.exe -m pip --version >nul 2>nul || rmdir /s /q venv
)
if exist pyexe.txt del pyexe.txt
if exist venv\Scripts\python.exe (
  set "PIPUSER="
) else (
  echo [!] Could not create a virtual environment - using the system Python instead.
  if exist venv rmdir /s /q venv
  python -c "import sys; print(sys.executable)" > pyexe.txt
  set "PIPUSER=--user"
)
call scripts\find_python.bat

REM ---------- 2. Packages ----------
echo Installing packages (first time takes a few minutes)...
"%PY%" -m pip install %PIPUSER% -q --disable-pip-version-check --timeout 60 -r requirements.txt || (echo [X] pip install failed - check the internet connection & pause & exit /b 1)

REM ---------- 3. Settings + database ----------
"%PY%" manage.py setup_local || (pause & exit /b 1)
echo.
echo Creating tables...
"%PY%" manage.py migrate --noinput || (echo [X] migrate failed & pause & exit /b 1)

REM ---------- 4. Move data from the cloud ----------
echo.
set "IMPORT=y"
set /p "IMPORT=Copy all data from Neon and download all files from Cloudinary now? This REPLACES the data on this PC. (Y/n): "
if /i "%IMPORT%"=="n" goto skip_import
"%PY%" manage.py import_from_cloud --yes || (echo [!] Import failed - see the message above. You can run 1_setup.bat again later. & goto skip_import)
echo.
echo Downloading pictures and videos to the media folder (may take a while)...
"%PY%" manage.py localize_media --cleanup
:skip_import

REM ---------- 5. Admin account ----------
"%PY%" manage.py shell -c "import sys; from django.contrib.auth.models import User; sys.exit(0 if User.objects.filter(is_superuser=True).exists() else 1)" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Create the admin account:
  "%PY%" manage.py createsuperuser
)

"%PY%" manage.py collectstatic --noinput >nul

echo.
echo =====================================================
echo   Setup finished.
echo   Next: run 2_start.bat to start the website
echo         run 3_autostart.bat (as administrator) to start it with Windows
echo =====================================================
pause
