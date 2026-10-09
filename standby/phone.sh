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
#   ★ للطوارئ (أمر واحد لكل اتجاه):
#   bash ~/iaj/standby/phone.sh takeover       # أحدث بيانات + تشغيل + تحويل iajaward.org إلى الهاتف
#   bash ~/iaj/standby/phone.sh handback       # (احتياط) رفع بيانات الهاتف يدوياً — ثم على السيرفر: back_to_server.bat
#   bash ~/iaj/standby/phone.sh server         # إعادة iajaward.org للسيرفر فوراً (بدون نقل بيانات)
#   bash ~/iaj/standby/phone.sh status         # أين يعمل iajaward.org الآن
#
#   bash ~/iaj/standby/phone.sh configure      # مرة واحدة: الرموز + أزرار على الشاشة الرئيسية (Termux:Widget)
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
    sed -i 's/\r$//' "$SITE"/standby/*.sh 2>/dev/null || true
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

  takeover)
    [ -f "$SITE/manage.py" ] || die "الكود غير موجود — شغّل: bash phone.sh update-code"
    [ -s "$HOME/.iaj_tunnel_token" ] || die "ضع رمز نفق الهاتف في ~/.iaj_tunnel_token أولاً"
    grep -q '^CF_API_TOKEN=.' "$SITE/.env" 2>/dev/null || die "ضع CF_API_TOKEN=... في $SITE/.env أولاً (رمز API من Cloudflare)"
    # إيقاف أي تشغيل قديم على الهاتف (حتى لا يتعارض مع المنفذ 8000)
    pkill -f "python serve.py" 2>/dev/null || true
    pkill -x cloudflared 2>/dev/null || true
    sleep 1
    bash "$0" restore
    cd "$SITE"
    termux-wake-lock 2>/dev/null || true
    say "تشغيل الموقع"
    python serve.py > "$HOME/iaj-serve.log" 2>&1 &
    WEB=$!
    OK=0
    for i in $(seq 1 60); do
      kill -0 $WEB 2>/dev/null || break
      python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/',timeout=2)" 2>/dev/null && { OK=1; break; }
      sleep 2
    done
    if [ $OK != 1 ]; then
      kill $WEB 2>/dev/null; tail -20 "$HOME/iaj-serve.log"
      die "الموقع لم يعمل على الهاتف — لم يُحوَّل شيء، iajaward.org ما زال على السيرفر"
    fi
    say "تشغيل نفق الهاتف"
    cloudflared tunnel --no-autoupdate run --token "$(cat "$HOME/.iaj_tunnel_token")" > "$HOME/cloudflared.log" 2>&1 &
    CF=$!
    FP0=$(python manage.py standby_fingerprint 2>/dev/null | tail -1)

    DONE=0
    finish() {
      [ $DONE = 1 ] && return; DONE=1
      kill $WEB $CF 2>/dev/null
      say "إيقاف الموقع على الهاتف"
      FP1=$(python manage.py standby_fingerprint 2>/dev/null | tail -1)
      if [ "$FP0" = "$FP1" ]; then
        # لم يُسجَّل شيء على الهاتف ← نعيد الموقع للسيرفر فوراً بلا نقل بيانات
        if python standby/cf_switch.py server; then
          echo "server $(date +%F_%H%M%S)" > "$LOCAL_BK/db/ACTIVE_SITE.txt"
          rclone copyto "$LOCAL_BK/db/ACTIVE_SITE.txt" "$REMOTE/db/ACTIVE_SITE.txt" 2>/dev/null || true
        else
          say "السيرفر غير متصل — iajaward.org سيبقى متوقفاً حتى يعود السيرفر أو تعيد تشغيل الطوارئ"
        fi
      else
        # سُجّلت بيانات على الهاتف ← نرفعها، والسيرفر يأخذها بـ back_to_server.bat
        bash "$0" backup || true
        echo
        echo "  ⚠ الآن على السيرفر شغّل:  back_to_server.bat  (ينقل بيانات الهاتف ويعيد الموقع)"
      fi
      termux-wake-unlock 2>/dev/null || true
    }
    trap finish EXIT INT TERM

    say "تحويل iajaward.org إلى الهاتف"
    if python standby/cf_switch.py phone; then
      NOW=$(python -c "from datetime import datetime;from zoneinfo import ZoneInfo;print(datetime.now(ZoneInfo('Asia/Amman')).strftime('%Y-%m-%d_%H%M%S'))")
      echo "phone $NOW" > "$LOCAL_BK/db/ACTIVE_SITE.txt"
      rclone copyto "$LOCAL_BK/db/ACTIVE_SITE.txt" "$REMOTE/db/ACTIVE_SITE.txt" 2>/dev/null || true
    else
      die "لم يتم التحويل — iajaward.org ما زال على السيرفر"
    fi
    say "✅ الهاتف يشغّل iajaward.org الآن — لا تغلق هذه النافذة. للإنهاء: Ctrl+C (يُعاد الموقع للسيرفر تلقائياً)"
    # مراقبة: إذا توقف الموقع أو النفق على الهاتف لأي سبب ← finish يعيد الموقع للسيرفر
    while kill -0 $WEB 2>/dev/null && kill -0 $CF 2>/dev/null; do sleep 5; done
    say "توقف الموقع أو النفق على الهاتف"
    exit 0
    ;;

  handback)
    bash "$0" backup
    echo
    echo "  الخطوة التالية على جهاز السيرفر (بعد عودة الإنترنت إليه): شغّل  back_to_server.bat"
    echo "  سيأخذ بيانات الهاتف من Drive ويعيد iajaward.org إلى السيرفر تلقائياً."
    ;;

  status)
    cd "$SITE" && python standby/cf_switch.py status
    ;;

  server)
    echo
    echo "  إعادة iajaward.org إلى السيرفر فوراً، بدون نقل أي بيانات من الهاتف."
    echo "  (إن كان الهاتف يشغّل الموقع وسُجّلت عليه بيانات: أوقفه بـ Ctrl+C في نافذته بدل هذا الزر)"
    read -r -p "  اكتب YES للمتابعة: " OK
    [ "$OK" = "YES" ] || die "تم الإلغاء"
    cd "$SITE" && python standby/cf_switch.py server && \
      echo "server $(date +%F_%H%M%S)" > "$LOCAL_BK/db/ACTIVE_SITE.txt" && \
      rclone copyto "$LOCAL_BK/db/ACTIVE_SITE.txt" "$REMOTE/db/ACTIVE_SITE.txt" 2>/dev/null || true
    ;;

  configure)
    ensure_env
    # ١) الرموز — تُكتب بدون أن تظهر على الشاشة
    if ! grep -q '^CF_API_TOKEN=.' "$SITE/.env"; then
      read -r -s -p "  الصق رمز Cloudflare API (iaj-switch) ثم Enter: " T; echo
      [ -n "$T" ] && echo "CF_API_TOKEN=$T" >> "$SITE/.env"
    fi
    if [ ! -s "$HOME/.iaj_tunnel_token" ]; then
      read -r -s -p "  الصق رمز نفق الهاتف (iaj-standby، يبدأ بـ eyJ) ثم Enter: " T; echo
      [ -n "$T" ] && printf '%s' "$T" > "$HOME/.iaj_tunnel_token" && chmod 600 "$HOME/.iaj_tunnel_token"
    fi
    chmod 600 "$SITE/.env" 2>/dev/null || true
    # ٢) أزرار جاهزة (تطبيق Termux:Widget من F-Droid يعرضها على الشاشة الرئيسية)
    mkdir -p "$HOME/.shortcuts"
    mk() { printf '#!/data/data/com.termux/files/usr/bin/bash\n%s\necho; read -r -p "اضغط Enter للإغلاق" _\n' "$2" > "$HOME/.shortcuts/$1"; chmod +x "$HOME/.shortcuts/$1"; }
    mk "IAJ 1 - تشغيل الطوارئ"  "bash ~/iaj/standby/phone.sh takeover"
    mk "IAJ 2 - إرجاع الموقع للسيرفر" "bash ~/iaj/standby/phone.sh server"
    mk "IAJ 3 - أين يعمل الموقع" "bash ~/iaj/standby/phone.sh status"
    mk "IAJ 4 - تحديث الكود"    "bash ~/iaj/standby/phone.sh update-code && bash ~/iaj/standby/phone.sh configure"
    rm -f "$HOME/.shortcuts/IAJ 2 - إنهاء الطوارئ"
    say "تم. الأزرار جاهزة في ~/.shortcuts — ثبّت Termux:Widget من F-Droid وأضف الأداة للشاشة الرئيسية"
    cd "$SITE" && python standby/cf_switch.py status || true
    ;;

  *)
    sed -n '3,22p' "$0"
    ;;
esac
