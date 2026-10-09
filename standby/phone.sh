#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  تشغيل موقع الجائزة من الهاتف (Termux) — جهاز احتياطي عند انقطاع الإنترنت عن السيرفر
#
#   bash ~/iaj/standby/phone.sh setup          # مرة واحدة: تثبيت المتطلبات
#   bash ~/iaj/standby/phone.sh update-code    # جلب آخر نسخة من الكود من Google Drive
#   bash ~/iaj/standby/phone.sh restore        # تنزيل أحدث نسخة بيانات + ملفات من Drive واسترجاعها
#   bash ~/iaj/standby/phone.sh start          # تشغيل الموقع على الهاتف فقط (تجربة: http://127.0.0.1:8000)
#   bash ~/iaj/standby/phone.sh start --public # تشغيل + ربطه بنفق الهاتف في Cloudflare (iaj-standby)
#   bash ~/iaj/standby/phone.sh backup         # رفع بيانات الهاتف إلى Drive (قبل الرجوع للسيرفر)
#
#  الإعدادات (اختياري) في ~/.iaj_standby:
#     REMOTE=gdrive:IAJ-backups      # اسم الاتصال في rclone + المجلد في Drive
#  رمز نفق الهاتف «iaj-standby» (نفق ثانٍ غير نفق السيرفر) في الملف: ~/.iaj_tunnel_token
#  أي عنوان يُوجَّه لهذا النفق من لوحة Cloudflare يعرض الموقع من الهاتف:
#    للتجربة: standby.iajaward.org — وعند الطوارئ: انقل iajaward.org إليه
# ================================================================
set -e
SITE="$HOME/iaj"
LOCAL_BK="$HOME/iaj-backups"
REMOTE="gdrive:IAJ-backups"
[ -f "$HOME/.iaj_standby" ] && . "$HOME/.iaj_standby"
export DATABASE_URL=""            # الهاتف يستخدم قاعدة SQLite محلية
export PYTHONUTF8=1

say() { printf '\n\033[1;33m» %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }

ensure_env() {
  # إعدادات الهاتف: بدون كلمات مرور البريد (الرسائل تُحفظ ولا تُرسل) — آمن للتجربة والطوارئ
  if [ ! -f "$SITE/.env" ]; then
    KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
    cat > "$SITE/.env" <<EOF
SECRET_KEY=$KEY
DEBUG=False
ALLOWED_HOSTS=*
SITE_URL=https://iajaward.org
CSRF_TRUSTED_ORIGINS=https://iajaward.org,https://www.iajaward.org
PORT=8000
THREADS=4
EOF
    say "أُنشئ ملف الإعدادات $SITE/.env (يمكنك نسخ إعدادات البريد من السيرفر إليه لاحقاً)"
  fi
}

case "$1" in
  setup)
    say "تثبيت Python والأدوات (قد يستغرق دقائق)"
    pkg update -y
    pkg install -y python python-pillow rclone cloudflared unzip
    pip install "Django==5.2.15" "whitenoise==6.12.0" "waitress==3.0.2" "dj-database-url==3.1.2" \
                requests django-quill-editor tzdata sqlparse asgiref
    termux-setup-storage || true
    say "تم. الخطوة التالية: اربط Google Drive بالأمر:  rclone config   (اسم الاتصال: gdrive)"
    ;;

  update-code)
    say "تنزيل الكود من $REMOTE/code"
    mkdir -p "$LOCAL_BK/code"
    rclone copy "$REMOTE/code" "$LOCAL_BK/code" --progress
    [ -f "$LOCAL_BK/code/iaj-code.zip" ] || die "لم أجد iaj-code.zip في Drive — شغّل backup_now.bat على السيرفر أولاً"
    unzip -oq "$LOCAL_BK/code/iaj-code.zip" -d "$HOME"
    say "تم تحديث الكود في $SITE"
    ;;

  restore)
    [ -f "$SITE/manage.py" ] || die "الكود غير موجود — شغّل: bash phone.sh update-code"
    ensure_env
    say "تنزيل أحدث نسخة بيانات من Drive"
    mkdir -p "$LOCAL_BK/db"
    rclone copy "$REMOTE/db" "$LOCAL_BK/db" --include "*.json.gz" --max-age 30d --progress
    say "تنزيل الصور والملفات (المرة الأولى أطول — بعدها الجديد فقط)"
    rclone copy "$REMOTE/media" "$SITE/media" --progress
    cd "$SITE"
    python manage.py restore_site --latest "$LOCAL_BK" --yes
    ;;

  start)
    [ -f "$SITE/manage.py" ] || die "الكود غير موجود — شغّل: bash phone.sh update-code"
    ensure_env
    cd "$SITE"
    termux-wake-lock 2>/dev/null || true      # منع الهاتف من إيقاف الموقع عند إطفاء الشاشة
    if [ "$2" = "--public" ]; then
      [ -s "$HOME/.iaj_tunnel_token" ] || die "ضع رمز النفق في ~/.iaj_tunnel_token أولاً"
      cloudflared tunnel --no-autoupdate run --token "$(cat "$HOME/.iaj_tunnel_token")" > "$HOME/cloudflared.log" 2>&1 &
      CF=$!
      trap 'kill $CF 2>/dev/null; termux-wake-unlock 2>/dev/null' EXIT
      say "نفق الهاتف يعمل — العناوين الموجّهة لنفق iaj-standby تعرض الموقع من هذا الهاتف (السجل: ~/cloudflared.log)"
    fi
    say "الموقع يعمل على http://127.0.0.1:8000 — للإيقاف: Ctrl+C"
    python serve.py
    ;;

  backup)
    [ -f "$SITE/manage.py" ] || die "الكود غير موجود"
    cd "$SITE"
    say "نسخ بيانات الهاتف"
    python manage.py backup_site --dir "$LOCAL_BK" --tag phone --no-code --no-media
    say "رفع النسخة والملفات الجديدة إلى Drive"
    rclone copy "$LOCAL_BK/db" "$REMOTE/db" --include "*-phone.json.gz" --max-age 1d --progress
    rclone copy "$SITE/media" "$REMOTE/media" --progress
    say "تم. على السيرفر: restore_backup.bat ← اختر 1 (نسخة الهاتف)، ثم أعد iajaward.org لنفق السيرفر من لوحة Cloudflare"
    ;;

  *)
    sed -n '3,16p' "$0"
    ;;
esac
