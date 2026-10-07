@echo off
chcp 65001 >nul
cd /d "%~dp0"
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1
"%PY%" manage.py backup_site
pause
