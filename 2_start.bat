@echo off
chcp 65001 >nul
title IAJ website - running (close this window to stop)
cd /d "%~dp0"
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1
if not exist .env (echo [X] Run 1_setup.bat first & pause & exit /b 1)
echo.
echo   Website : http://localhost:8000/
echo   Admin   : http://localhost:8000/admin/
echo   Same network (phone etc): http://THIS-PC-IP:8000/   (ipconfig shows the IP)
echo   Close this window to stop the website.
echo.
"%PY%" serve.py
pause
