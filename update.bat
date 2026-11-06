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
"%PY%" manage.py build_icons_js >nul 2>nul
"%PY%" manage.py collectstatic --noinput >nul

REM إعادة تشغيل الموقع إن كان يعمل تلقائياً مع Windows
schtasks /query /tn "IAJ Website" >nul 2>nul
if errorlevel 1 goto manual
net session >nul 2>nul || (echo. & echo [!] To restart the website automatically, run this file as administrator. Or restart the PC. & pause & exit /b 0)
REM مهمة التشغيل معطّلة (لا يبدأ مع ويندوز) والنظام يعمل: يُعاد تشغيله بالنسخة الجديدة وتبقى المهمة معطّلة.
REM معطّلة والنظام متوقف (استُعمل ملف الإيقاف): لا يُشغَّل.
set "TN=IAJ Website"
set "WASOFF="
set "WASRUN="
schtasks /query /tn "%TN%" /fo list /v | findstr /i /c:"Scheduled Task State:" | findstr /i "Disabled" >nul && set "WASOFF=1"
schtasks /query /tn "%TN%" /fo list | findstr /i /c:"Status:" | findstr /i "Running" >nul && set "WASRUN=1"
if defined WASOFF if not defined WASRUN goto off
schtasks /end /tn "%TN%" >nul 2>nul
REM انتظار ثانيتين (ping يعمل حتى عند تحويل الإدخال، بخلاف timeout)
ping -n 3 127.0.0.1 >nul
if defined WASOFF schtasks /change /tn "%TN%" /enable >nul
schtasks /run /tn "%TN%" >nul 2>nul
set "RC=%errorlevel%"
if defined WASOFF schtasks /change /tn "%TN%" /disable >nul
if not "%RC%"=="0" (echo. & echo [X] The new version could not be started. If it was switched off, run iaj_on.bat as administrator - or 2_start.bat to see the error. & pause & exit /b 1)
echo.
echo Done. The website was restarted with the new version.
if defined WASOFF echo It still does not start with Windows ^(its startup task stays disabled^).
pause
exit /b 0
:off
echo.
echo Code updated. The website is switched OFF ^(its startup task is disabled^), so it was not started.
echo To turn it on: run iaj_on.bat as administrator - or 2_start.bat for this session only.
pause
exit /b 0

:manual
echo.
echo Done. Close the website window (2_start.bat) and open it again to use the new version.
pause
