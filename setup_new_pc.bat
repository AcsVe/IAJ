@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title اعادة بناء الانظمة على ويندوز (جهاز جديد او بعد اعادة التهيئة)
REM ================================================================
REM  يعيد بناء الانظمة الاربعة على ويندوز بترتيب واحد:
REM  يثبّت الادوات -> يستنسخ الاكواد -> 1_setup ثم 3_autostart لكل نظام
REM  شغّله بزر يمين > Run as administrator
REM ================================================================

REM ---- يجب التشغيل كمسؤول (3_autostart يحتاج ذلك) ----
net session >nul 2>nul || (echo [X] شغّل هذا الملف بزر اليمين ثم "Run as administrator". & pause & exit /b 1)

REM ---- مجلدات التثبيت (عدّلها إن أردت) ----
set "IAJ_DIR=C:\IAJ"
set "ATT_DIR=C:\Att"
set "TKT_DIR=C:\TKT"
set "VEN_DIR=C:\Venue"

echo =====================================================
echo   الخطوة 1: تثبيت الادوات المطلوبة (يتخطى المثبّت)
echo =====================================================
where winget >nul 2>nul || (echo [X] winget غير متوفر. ثبّت "App Installer" من Microsoft Store ثم اعد المحاولة. & pause & exit /b 1)

set "NEEDREOPEN="
where git        >nul 2>nul || (echo تثبيت Git...        & winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
where python     >nul 2>nul || (echo تثبيت Python 3.12...& winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
where cloudflared>nul 2>nul || (echo تثبيت cloudflared...& winget install -e --id Cloudflare.cloudflared --accept-source-agreements --accept-package-agreements & set "NEEDREOPEN=1")
REM Google Drive for desktop: يوفّر مجلد النسخ الاحتياطي IAJ-backups
winget list --id Google.GoogleDrive >nul 2>nul || (echo تثبيت Google Drive for desktop...& winget install -e --id Google.GoogleDrive --accept-source-agreements --accept-package-agreements)

echo.
echo [ملاحظة] نظام IAJ وحده يحتاج PostgreSQL. ان لم يكن مثبتاً نفّذ لاحقاً:
echo          winget install -e --id PostgreSQL.PostgreSQL.16
echo          واحفظ كلمة مرور المستخدم postgres (يطلبها 1_setup الخاص بـ IAJ).

if defined NEEDREOPEN (
  echo.
  echo =====================================================
  echo   تم تثبيت ادوات جديدة. اغلق هذه النافذة ثم شغّل
  echo   الملف مرة اخرى "Run as administrator" لاكمال الباقي.
  echo =====================================================
  pause & exit /b 0
)

echo.
echo =====================================================
echo   الخطوة 2: تنزيل الاكواد من GitHub
echo =====================================================
set "TK="
set /p "TK=الصق رمز GitHub (Fine-grained . Contents: Read) ثم Enter: "
if "%TK%"=="" (echo [X] بدون رمز لا يمكن المتابعة. & pause & exit /b 1)

call :clone "%IAJ_DIR%" IAJ
call :clone "%ATT_DIR%" Attendance
call :clone "%TKT_DIR%" RASTKT
call :clone "%VEN_DIR%" venues
set "TK="

echo.
echo =====================================================
echo   الخطوة 3: اعداد كل نظام (IAJ اولاً)
echo   سيطلب كل نظام اعداداته الخاصة (.env والبيانات)
echo =====================================================
call :prep "%IAJ_DIR%"
call :prep "%ATT_DIR%"
call :prep "%TKT_DIR%"
call :prep "%VEN_DIR%"

echo.
echo =====================================================
echo   تم. تحقّق بفتح: award / 1 / 2 / 3 .iajaward.org
echo   او شغّل site_where.bat داخل اي مجلد.
echo =====================================================
pause
exit /b 0

:clone
set "D=%~1"
set "REPO=%~2"
if exist "%D%\.git" (
  echo تحديث %D% ...
  git -C "%D%" remote set-url origin https://%TK%@github.com/AcsVe/%REPO%.git
  git -C "%D%" fetch origin main && git -C "%D%" reset --hard origin/main
) else (
  echo تنزيل %REPO% الى %D% ...
  git clone https://%TK%@github.com/AcsVe/%REPO%.git "%D%" || (echo [!] تعذّر تنزيل %REPO% - تحقّق ان الرمز يشمله.)
)
if exist "%D%\.git" git -C "%D%" remote set-url origin https://github.com/AcsVe/%REPO%.git
exit /b 0

:prep
set "D=%~1"
if not exist "%D%\1_setup.bat" (echo [تخطّي] %D% غير موجود & exit /b 0)
echo.
echo --- اعداد %D% ---
pushd "%D%"
call 1_setup.bat
call 3_autostart.bat
popd
exit /b 0
