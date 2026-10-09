@echo off
chcp 65001 >nul
cd /d "%~dp0"
call scripts\find_python.bat
set PYTHONUTF8=1
REM Point iajaward.org back to THIS server right now (no data is moved)
"%PY%" standby\cf_switch.py server
echo.
pause
