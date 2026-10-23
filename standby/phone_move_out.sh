#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  نقل Termux إلى هاتف جديد — الخطوة 1 على الهاتف القديم
#
#   curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_out.sh | bash
#
#  يصنع ملفاً واحداً مشفّراً (كلمة مرور تختارها) فيه كل ما في البيت:
#  كود الأنظمة وبياناتها، الأزرار، Termux:Boot، رموز الأنفاق وGitHub وrclone، ‎.ssh،
#  وقائمة الحزم (pkg / pip / npm) والخدمات، ونسخة SQL من قواعد PostgreSQL.
#  الملف: مجلد التنزيلات (Downloads) ← termux-move-<التاريخ>.tgz.enc
#  ثم على الهاتف الجديد: phone_move_in.sh
# ================================================================
set -e
say() { printf '\n\033[1;36m» %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
MOVE="$HOME/.move"
STAMP=$(date +%Y-%m-%d_%H%M)
# مجلدات قديمة كبيرة لا تُنقل (أضف ALL=1 لنقلها أيضاً)
SKIP_OLD="ars-booking-app helpdesk acs-booking"

pgrep -f "standby/phone.sh (takeover|start)" >/dev/null 2>&1 && \
  die "يوجد نظام يعمل الآن من الهاتف (طوارئ) — أنهِه أولاً من زر «… 1 - إنهاء» ثم أعد الأمر"

command -v openssl >/dev/null || pkg install -y openssl-tool >/dev/null
[ -d "$HOME/storage/downloads" ] || { termux-setup-storage; sleep 4; }
[ -d "$HOME/storage/downloads" ] || die "لا أصل إلى مجلد التنزيلات — اسمح لـ Termux بالوصول إلى الملفات ثم أعد الأمر"

rm -rf "$MOVE"; mkdir -p "$MOVE"
say "1) قائمة الحزم والمكتبات والخدمات"
apt-mark showmanual 2>/dev/null | sort > "$MOVE/pkgs.txt"
pip list --format=freeze 2>/dev/null > "$MOVE/pip.txt" || true
npm ls -g --depth=0 --parseable 2>/dev/null | tail -n +2 | sed 's#.*/node_modules/##' | grep -v '^npm$' > "$MOVE/npm.txt" || true
for s in "$PREFIX"/var/service/*/; do
  n=$(basename "$s"); [ -f "$s/down" ] || echo "$n"
done > "$MOVE/services.txt" 2>/dev/null || true
uname -m > "$MOVE/arch.txt"; date '+%F %T' > "$MOVE/created.txt"

say "2) إزالة أي رمز مكتوب داخل عناوين مستودعات git (لا يُنقل رمز مكشوف)"
for d in "$HOME" "$HOME"/*/; do
  u=$(git -C "$d" remote get-url origin 2>/dev/null) || continue
  case "$u" in https://*@*)
    clean="https://${u#*@}"
    git -C "$d" remote set-url origin "$clean"
    echo "  ✓ $(basename "$d"): أُزيل الرمز من العنوان — ألغِ ذلك الرمز من GitHub" ;;
  esac
done

say "3) نسخة SQL من قواعد PostgreSQL ثم إيقافها (لنسخ ملفاتها سليمة)"
for PGD in "$HOME/timetable-pg" "$PREFIX/var/lib/postgresql"; do
  [ -f "$PGD/PG_VERSION" ] || continue
  tag=$(basename "$PGD")
  started=0
  if ! pg_ctl -D "$PGD" status >/dev/null 2>&1; then
    rm -f "$PGD/postmaster.pid"
    pg_ctl -D "$PGD" -l "$MOVE/pg-$tag.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null 2>&1 && started=1 || true
    PORT=5499
  else
    PORT=$(sed -n 4p "$PGD/postmaster.pid" 2>/dev/null); PORT=${PORT:-5432}
  fi
  if pg_dumpall -h 127.0.0.1 -p "$PORT" -U postgres > "$MOVE/pg-$tag.sql" 2>/dev/null \
     || pg_dumpall -h 127.0.0.1 -p "$PORT" > "$MOVE/pg-$tag.sql" 2>/dev/null; then
    echo "  ✓ $tag: $(du -h "$MOVE/pg-$tag.sql" | cut -f1)"
  else
    echo "  ⚠ $tag: تعذّرت نسخة SQL — تُنقل ملفات القاعدة فقط"; rm -f "$MOVE/pg-$tag.sql"
  fi
  cat "$PGD/PG_VERSION" > "$MOVE/pg-$tag.version"
  pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
  [ $started = 1 ] || echo "  (أُوقفت؛ أعد تشغيلها بعد الانتهاء إن احتجت: sv up postgres أو زر النظام)"
done

say "4) كلمة مرور الملف (تحتاجها على الهاتف الجديد — لا تُرسلها مع الملف)"
while true; do
  read -r -s -p "  كلمة المرور (8 أحرف على الأقل): " P1 </dev/tty; echo
  read -r -s -p "  أعد كتابتها: " P2 </dev/tty; echo
  [ ${#P1} -ge 8 ] && [ "$P1" = "$P2" ] && break
  echo "  - قصيرة أو غير متطابقة"
done
export MOVE_PASS="$P1"

OUT="$HOME/storage/downloads/termux-move-$STAMP.tgz.enc"
EX=(--exclude=./storage --exclude=./.cache --exclude=./.npm --exclude=./.bash_history --exclude='*/__pycache__'
    --exclude='*/node_modules' --exclude='./*/logs/*.log' --exclude='./*.log')
if [ "$ALL" != 1 ]; then for d in $SKIP_OLD; do EX+=(--exclude="./$d"); done; fi
say "5) ضغط البيت وتشفيره — قد يستغرق دقائق"
cd "$HOME"
tar -czf - "${EX[@]}" . | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:MOVE_PASS -out "$OUT"
unset MOVE_PASS P1 P2
SUM=$(sha256sum "$OUT" | cut -c1-16)
rm -rf "$MOVE"

say "✅ جاهز: $(du -h "$OUT" | cut -f1)  —  التنزيلات/$(basename "$OUT")  (البصمة $SUM)"
echo "  لم يُنقل: $SKIP_OLD (مجلدات قديمة) — لنقلها: ALL=1 bash phone_move_out.sh"
if rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
  read -r -p "  رفع الملف المشفّر إلى Drive أيضاً (gdrive:IAJ-backups/phone-move)? (y/N): " UP </dev/tty
  if [ "$UP" = y ] || [ "$UP" = Y ]; then
    rclone copy "$OUT" gdrive:IAJ-backups/phone-move --progress && echo "  ✓ رُفع إلى Drive" || echo "  ⚠ تعذّر الرفع — انقل الملف يدوياً"
  fi
fi
echo
echo "  التالي: انقل الملف إلى مجلد التنزيلات في الهاتف الجديد (كابل، Drive، أو مشاركة قريبة)، ثم فيه:"
echo "  curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_in.sh | bash"
echo "  ⚠ لا تشغّل الطوارئ من الهاتفين معاً."
