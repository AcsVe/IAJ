@echo off
chcp 65001 >nul
cd /d "%~dp0"
title IAJ - Restore latest backup
call scripts\find_python.bat
set PYTHONUTF8=1
echo.
echo   ==========================================================
echo    Restore a backup (from BACKUP_DIR in .env)
echo.
echo    [1] Latest backup made by the PHONE  (use this when switching back
echo        to this PC after the phone was serving the website)
echo    [2] Latest backup of any device
echo.
echo    WARNING: all current website data on THIS PC will be replaced.
echo   ==========================================================
echo.
set /p CH=Choose 1 or 2: 
set TAG=
if "%CH%"=="1" set TAG=--tag phone
if not "%CH%"=="1" if not "%CH%"=="2" (echo   Cancelled. & pause & exit /b 0)
set /p OK=Type YES to continue: 
if /i not "%OK%"=="YES" (echo   Cancelled. & pause & exit /b 0)
schtasks /end /tn "IAJ Website" >nul 2>nul
"%PY%" manage.py restore_site --latest auto %TAG% --media --yes
if errorlevel 1 (echo. & echo   [X] Restore failed - see the message above & pause & exit /b 1)
schtasks /run /tn "IAJ Website" >nul 2>nul
echo.
echo   Done. The website is running with the restored data.
pause
