@echo off
chcp 65001 >nul
title IAJ - Simulation
cd /d "%~dp0"
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1
REM محاكاة دورة كاملة ببيانات وهمية (دورة منفصلة، لا بريد) + تقرير نجح/فشل
"%PY%" manage.py simulate_cycle
echo.
echo To erase all simulation data run simulate_clear.bat
pause
