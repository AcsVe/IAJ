@echo off
chcp 65001 >nul
title IAJ - Clear simulation
cd /d "%~dp0"
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1
REM مسح كل بيانات التجربة والمحاكاة (تُحفظ نسخة مما يُحذف في backups\deleted)
"%PY%" manage.py simulate_cycle --clear
pause
