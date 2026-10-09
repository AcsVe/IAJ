@echo off
chcp 65001 >nul
cd /d "%~dp0"
title IAJ - Back to this server
call scripts\find_python.bat
set PYTHONUTF8=1
echo.
echo   ==========================================================
echo    Move iajaward.org back to THIS server
echo    1) bring the phone's data from Google Drive into this server
echo    2) point iajaward.org back to this server (Cloudflare)
echo.
echo    Before this: on the phone press Ctrl+C, then run:
echo        bash ~/iaj/standby/phone.sh handback
echo   ==========================================================
echo.
set /p OK=Type YES to continue: 
if /i not "%OK%"=="YES" (echo   Cancelled. & pause & exit /b 0)
schtasks /end /tn "IAJ Website" >nul 2>nul
"%PY%" manage.py standby_return
if errorlevel 1 (schtasks /run /tn "IAJ Website" >nul 2>nul & echo. & echo   [X] Not finished - see the message above & pause & exit /b 1)
schtasks /run /tn "IAJ Website" >nul 2>nul
timeout /t 8 /nobreak >nul
"%PY%" standby\cf_switch.py server
echo.
pause
