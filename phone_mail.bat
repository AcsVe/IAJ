@echo off
chcp 65001 >nul
cd /d "%~dp0"
call scripts\find_python.bat
set PYTHONUTF8=1
echo.
echo  Email settings of every system -^> encrypted file in Google Drive for the standby phone
echo.
"%PY%" standby\mail_bundle.py export
echo.
pause
