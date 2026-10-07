@echo off
chcp 65001 >nul
title IAJ - Update from GitHub
cd /d "%~dp0"
REM يسحب آخر تحديث للكود من GitHub — البيانات (.env, media, backups) لا تُلمس أبداً
where git >nul 2>nul || (echo [X] Git is not installed. Install it from https://git-scm.com/download/win then run this file again. & pause & exit /b 1)
call scripts\find_python.bat
set DATABASE_URL=
set PYTHONUTF8=1

if not exist .git (
  echo First time: linking this folder to GitHub...
  git init -q
  git remote add origin https://github.com/AcsVe/IAJ.git
  git fetch -q origin main || (echo [X] Could not reach GitHub & pause & exit /b 1)
  git reset -q --hard origin/main
  git branch -q -M main
  git branch -q --set-upstream-to=origin/main main
) else (
  echo Downloading the latest version...
  git fetch -q origin main || (echo [X] Could not reach GitHub & pause & exit /b 1)
  git reset -q --hard origin/main
)
echo Now at:
git log -1 --oneline

echo Installing new packages if needed...
"%PY%" -m pip install -q --disable-pip-version-check -r requirements.txt
echo Updating database tables...
"%PY%" manage.py migrate --noinput || (echo [X] migrate failed & pause & exit /b 1)
"%PY%" manage.py collectstatic --noinput >nul

REM إعادة تشغيل الموقع إن كان يعمل تلقائياً مع Windows
schtasks /query /tn "IAJ Website" >nul 2>nul
if errorlevel 1 goto manual
net session >nul 2>nul || (echo. & echo [!] To restart the website automatically, run this file as administrator. Or restart the PC. & pause & exit /b 0)
schtasks /end /tn "IAJ Website" >nul 2>nul
timeout /t 2 >nul
schtasks /run /tn "IAJ Website" >nul
echo.
echo Done. The website was restarted with the new version.
pause
exit /b 0

:manual
echo.
echo Done. Close the website window (2_start.bat) and open it again to use the new version.
pause
