@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Rebuild the systems on Windows (new PC or after a reset)
REM ================================================================
REM  يعيد بناء الأنظمة الأربعة على ويندوز بترتيب واحد:
REM  يثبّت الأدوات ← يستنسخ الأكواد ← 1_setup ثم 3_autostart لكل نظام
REM  يُشغَّل بزر الفأرة الأيمن ← Run as administrator
REM  نصوص النافذة بالإنجليزية لأن نافذة الأوامر لا تعرض العربية سليمة
REM ================================================================

REM ---- يلزم التشغيل كمسؤول (يحتاجه 3_autostart) ----
net session >nul 2>nul || (echo [X] Right-click this file and choose "Run as administrator". & pause & exit /b 1)

REM ---- مجلدات التثبيت (كما على كمبيوتر المدرسة) ----
set "IAJ_DIR=C:\IAJ"
set "ATT_DIR=C:\Att"
set "TKT_DIR=C:\RASTKT"
set "VEN_DIR=C:\venues"

echo =====================================================
echo   Step 1: install the required tools (skips what is installed)
echo =====================================================
where winget >nul 2>nul || (echo [X] winget is missing. Install "App Installer" from the Microsoft Store, then run this file again. & pause & exit /b 1)

set "NEEDREOPEN="
where git        >nul 2>nul || (echo Installing Git...        & winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
where python     >nul 2>nul || (echo Installing Python 3.12...& winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
where cloudflared>nul 2>nul || (echo Installing cloudflared...& winget install -e --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
REM Google Drive for desktop: يوفّر مجلد النسخ الاحتياطية IAJ-backups
winget list --id Google.GoogleDrive >nul 2>nul || (echo Installing Google Drive for desktop...& winget install -e --id Google.GoogleDrive --accept-source-agreements --accept-package-agreements)

echo.
echo [Note] Only the award site (IAJ) needs PostgreSQL. If it is not installed, run later:
echo          winget install -e --id PostgreSQL.PostgreSQL.16
echo          and keep the password of the user postgres (the IAJ 1_setup asks for it).

if defined NEEDREOPEN (
  echo.
  echo =====================================================
  echo   New tools were installed. Close this window, then run
  echo   this file again with "Run as administrator" to finish.
  echo =====================================================
  pause & exit /b 0
)

echo.
echo =====================================================
echo   Step 2: download the code from GitHub
echo =====================================================
set "TK="
REM المستودعات عامة: الرمز اختياري (يُستعمل فقط إن كان أحدها خاصاً)، ولا يُحفظ بعد التحميل
set /p "TK=GitHub token, only if a repository is private (otherwise just press Enter): "

call :clone "%IAJ_DIR%" IAJ
call :clone "%ATT_DIR%" Attendance
call :clone "%TKT_DIR%" RASTKT
call :clone "%VEN_DIR%" venues
set "TK="

echo.
echo =====================================================
echo   Step 3: set up each system (IAJ first)
echo   Each system asks for its own settings (.env and data)
echo =====================================================
call :prep "%IAJ_DIR%"
call :prep "%ATT_DIR%"
call :prep "%TKT_DIR%"
call :prep "%VEN_DIR%"

echo.
echo =====================================================
echo   Done. Check: iajaward.org, 1, 2 and 3 .iajaward.org
echo   or run site_where.bat inside any of the folders.
echo =====================================================
pause
exit /b 0

:clone
set "D=%~1"
set "REPO=%~2"
set "URL=https://github.com/AcsVe/%REPO%.git"
if defined TK set "URL=https://%TK%@github.com/AcsVe/%REPO%.git"
if exist "%D%\.git" (
  echo Updating %D% ...
  git -C "%D%" remote set-url origin "%URL%"
  git -C "%D%" fetch origin main && git -C "%D%" reset --hard origin/main
) else (
  echo Downloading %REPO% to %D% ...
  git clone "%URL%" "%D%" || (echo [!] Could not download %REPO% - check the internet connection, or the token if the repository is private.)
)
set "URL="
if exist "%D%\.git" git -C "%D%" remote set-url origin https://github.com/AcsVe/%REPO%.git
exit /b 0

:prep
set "D=%~1"
if not exist "%D%\1_setup.bat" (echo [Skip] %D% is missing & exit /b 0)
echo.
echo --- Setting up %D% ---
pushd "%D%"
call 1_setup.bat
call 3_autostart.bat
popd
exit /b 0
