@echo off
chcp 65001 >nul
title IAJ - Copy data from Neon and files from Cloudinary
cd /d "%~dp0"
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1
if not exist .env (echo [X] Run 1_setup.bat first & pause & exit /b 1)
echo This REPLACES all data on this PC with the data from Neon.
set "OK=y"
set /p "OK=Continue? (Y/n): "
if /i "%OK%"=="n" exit /b 0
"%PY%" manage.py migrate --noinput || (echo [X] migrate failed & pause & exit /b 1)
"%PY%" manage.py import_from_cloud --yes || (echo [X] Import failed - send the message above & pause & exit /b 1)
echo.
echo Downloading pictures and videos to the media folder (may take a while)...
"%PY%" manage.py localize_media --cleanup
echo.
echo Done. Log in to /admin with the same account you used on the old site.
pause
