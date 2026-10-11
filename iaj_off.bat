@echo off
chcp 65001 >nul
title IAJ - Turn the award website OFF
net session >nul 2>nul || (echo [X] Right-click this file and choose "Run as administrator". & pause & exit /b 1)
REM Stops iajaward.org only - the ticket system (1.iajaward.org) keeps running
schtasks /end /tn "IAJ Website" >nul 2>nul
schtasks /change /tn "IAJ Website" /disable >nul 2>nul
echo.
echo   iajaward.org is OFF (also after restarting the PC).
echo   1.iajaward.org (tickets) is still running.
echo   To turn it back on: iaj_on.bat (as administrator)
echo.
pause
