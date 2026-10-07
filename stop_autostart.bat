@echo off
cd /d "%~dp0"
net session >nul 2>nul || (echo [X] Right-click this file and choose "Run as administrator". & pause & exit /b 1)
schtasks /end /tn "IAJ Website" >nul 2>nul
schtasks /delete /f /tn "IAJ Website" >nul 2>nul
schtasks /delete /f /tn "IAJ Daily Backup" >nul 2>nul
echo Website stopped and removed from Windows startup (data and files are kept).
pause
