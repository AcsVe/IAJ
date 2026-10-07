@echo off
chcp 65001 >nul
title IAJ - Start with Windows + daily backup
cd /d "%~dp0"
net session >nul 2>nul || (echo [X] Right-click this file and choose "Run as administrator". & pause & exit /b 1)
call scripts\find_python.bat
if not exist .env (echo [X] Run 1_setup.bat first & pause & exit /b 1)

REM full path of python (find_python may return just "python")
"%PY%" -c "import sys; print(sys.executable)" > "%TEMP%\iaj_py.txt"
set /p PYFULL=<"%TEMP%\iaj_py.txt"
set "SITE=%~dp0"
set "SITE=%SITE:~0,-1%"

REM With the virtual environment the site runs as a Windows service account at boot.
REM Without it (packages installed for this user only) it runs when you log in.
if exist venv\Scripts\python.exe (
  set "WHEN=/sc onstart /ru SYSTEM"
  set "BKRU=/ru SYSTEM"
) else (
  set "WHEN=/sc onlogon /ru %USERNAME% /it"
  set "BKRU=/ru %USERNAME% /it"
)

schtasks /end /tn "IAJ Website" >nul 2>nul
schtasks /create /f /tn "IAJ Website" %WHEN% /rl highest /tr "\"%PYFULL%\" \"%SITE%\serve.py\"" || (echo [X] Could not create the startup task & pause & exit /b 1)
schtasks /create /f /tn "IAJ Daily Backup" /sc daily /st 02:00 %BKRU% /rl highest /tr "\"%PYFULL%\" \"%SITE%\manage.py\" backup_site" >nul || echo [!] Could not create the backup task

REM open port 8000 for devices on the same network
netsh advfirewall firewall delete rule name="IAJ Website" >nul 2>nul
netsh advfirewall firewall add rule name="IAJ Website" dir=in action=allow protocol=TCP localport=8000 profile=private,domain >nul

REM keep the PC awake while plugged in (a sleeping PC = website offline)
powercfg /change standby-timeout-ac 0 >nul 2>nul
powercfg /change hibernate-timeout-ac 0 >nul 2>nul

schtasks /run /tn "IAJ Website" >nul
echo.
echo   Done. The website starts automatically with Windows.
echo   Backup runs every day at 02:00 (folder: backups).
echo   Log file: logs\server.log
echo   Sleep is turned off while the PC is plugged in.
echo   To stop it: run stop_autostart.bat as administrator.
timeout /t 5 >nul
start "" http://localhost:8000/
pause
