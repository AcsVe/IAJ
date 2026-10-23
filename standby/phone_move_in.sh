#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  نقل Termux إلى هاتف جديد — الخطوة 2 على الهاتف الجديد
#
#  قبلها: ثبّت Termux وTermux:API وTermux:Widget وTermux:Boot من المصدر نفسه (F-Droid أو GitHub)،
#  وافتح Termux:Boot مرة واحدة، وضع ملف termux-move-*.tgz.enc في مجلد التنزيلات.
#
#   curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_in.sh | bash
#   (أو مع مسار الملف: … | bash -s /sdcard/Download/termux-move-….tgz.enc)
# ================================================================
set -e
say() { printf '\n\033[1;36m» %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
MOVE="$HOME/.move"

say "1) تجهيز Termux"
yes | pkg update -y >/dev/null 2>&1 || pkg update -y
pkg install -y openssl-tool tar termux-services >/dev/null
[ -d "$HOME/storage/downloads" ] || { termux-setup-storage; sleep 5; }

F="$1"
[ -n "$F" ] || F=$(ls -t "$HOME"/storage/downloads/termux-move-*.tgz.enc /sdcard/Download/termux-move-*.tgz.enc 2>/dev/null | head -1)
[ -f "$F" ] || die "لم أجد ملف termux-move-*.tgz.enc في التنزيلات — انقله إليها ثم أعد الأمر"
echo "  الملف: $F ($(du -h "$F" | cut -f1)، البصمة $(sha256sum "$F" | cut -c1-16))"

if [ -n "$(ls -A "$HOME" 2>/dev/null | grep -v '^storage$\|^\.termux$\|^\.bash_history$')" ]; then
  echo "  ⚠ البيت ليس فارغاً؛ الملفات التي تحمل الاسم نفسه ستُستبدل."
  read -r -p "  متابعة؟ اكتب YES: " OK </dev/tty
  [ "$OK" = YES ] || die "تم الإلغاء"
fi

say "2) فك التشفير والاسترجاع"
for i in 1 2 3; do
  read -r -s -p "  كلمة مرور الملف: " MOVE_PASS </dev/tty; echo; export MOVE_PASS
  if openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:MOVE_PASS -in "$F" | tar -xzf - -C "$HOME" 2>"$HOME/.move-err"; then
    ok=1; break
  fi
  echo "  - كلمة مرور خاطئة أو ملف ناقص"; ok=0
done
unset MOVE_PASS
[ "$ok" = 1 ] || die "تعذّر الاسترجاع: $(tail -2 "$HOME/.move-err")"
rm -f "$HOME/.move-err"
[ -d "$MOVE" ] || die "الملف لا يحوي قائمة الحزم (.move) — هل صُنع بـ phone_move_out.sh؟"
[ "$(cat "$MOVE/arch.txt")" = "$(uname -m)" ] || echo "  ⚠ معالج مختلف ($(cat "$MOVE/arch.txt") ← $(uname -m)) — المكتبات تُثبَّت من جديد على أي حال"

say "3) الحزم (pkg)"
grep -qx tur-repo "$MOVE/pkgs.txt" && pkg install -y tur-repo >/dev/null 2>&1 && pkg update -y >/dev/null 2>&1 || true
grep -qx sshd "$MOVE/services.txt" && echo openssh >> "$MOVE/pkgs.txt"
if ! pkg install -y $(cat "$MOVE/pkgs.txt") >/dev/null 2>&1; then
  for p in $(cat "$MOVE/pkgs.txt"); do pkg install -y "$p" >/dev/null 2>&1 || echo "  ⚠ لم تُثبَّت: $p"; done
fi

say "4) مكتبات Python (pip)"
# ما تثبّته pkg لا يُعاد بـ pip (يُبنى خصيصاً لـ Termux)
grep -viE '^(pip|numpy|pandas|pillow|cryptography|cffi|pycparser|lxml)==' "$MOVE/pip.txt" > "$MOVE/pip-req.txt" || true
if ! pip install -q -r "$MOVE/pip-req.txt" 2>/dev/null; then
  while read -r line; do
    [ -n "$line" ] || continue
    pip install -q "$line" 2>/dev/null || pip install -q "${line%%==*}" 2>/dev/null || echo "  ⚠ لم تُثبَّت: $line"
  done < "$MOVE/pip-req.txt"
fi

if [ -s "$MOVE/npm.txt" ]; then
  say "5) أدوات npm"
  npm install -g $(cat "$MOVE/npm.txt") >/dev/null 2>&1 || echo "  ⚠ تعذّر بعضها: $(tr '\n' ' ' < "$MOVE/npm.txt")"
fi

say "6) قواعد PostgreSQL"
for PGD in "$HOME/timetable-pg" "$PREFIX/var/lib/postgresql"; do
  tag=$(basename "$PGD"); dump="$MOVE/pg-$tag.sql"
  [ -f "$dump" ] || [ -f "$PGD/PG_VERSION" ] || continue
  rm -f "$PGD/postmaster.pid"
  if [ -f "$PGD/PG_VERSION" ] && pg_ctl -D "$PGD" -l "$HOME/pg-move.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null 2>&1; then
    pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
    echo "  ✓ $tag: ملفات القاعدة تعمل كما هي"
    continue
  fi
  [ -f "$dump" ] || { echo "  ⚠ $tag: لا تعمل ولا توجد نسخة SQL"; continue; }
  [ -d "$PGD" ] && mv "$PGD" "$PGD.old-$(date +%s)"
  initdb -D "$PGD" -U postgres --auth=trust -E UTF8 --locale=C >/dev/null
  pg_ctl -D "$PGD" -l "$HOME/pg-move.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null
  psql -q -h 127.0.0.1 -p 5499 -U postgres -d postgres -f "$dump" >/dev/null 2>"$HOME/pg-move-restore.log" || true
  pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
  echo "  ✓ $tag: أُنشئت من جديد واستُرجعت من نسخة SQL (النسخة القديمة في $PGD.old-*)"
done

say "7) الخدمات والأذونات"
for s in $(cat "$MOVE/services.txt" 2>/dev/null); do sv-enable "$s" >/dev/null 2>&1 && echo "  ✓ $s" || echo "  ⚠ $s (فعّلها بعد إعادة فتح Termux: sv-enable $s)"; done
chmod 600 "$HOME"/.*_token "$HOME"/.*_standby 2>/dev/null || true
chmod 700 "$HOME/.ssh" 2>/dev/null && chmod 600 "$HOME"/.ssh/* 2>/dev/null || true
chmod +x "$HOME"/.shortcuts/* "$HOME"/.termux/boot/* 2>/dev/null || true
for f in "$HOME"/*/standby/*.sh; do sed -i 's/\r$//' "$f" 2>/dev/null || true; done
rm -rf "$MOVE"

say "✅ اكتمل النقل"
cat <<'EOF'
  بقي على الهاتف الجديد:
  1. أغلق Termux وافتحه من جديد (لتعمل الخدمات)، ثم حدّث أداة Termux:Widget لتظهر الأزرار.
  2. أوقف «تحسين البطارية» لـ Termux وTermux:Boot من إعدادات أندرويد.
  3. جرّب: زر «IAJ 3 - أين يعمل الموقع» ثم «IAJ 8 - تجربة على الهاتف فقط».
  4. احذف ملف termux-move-*.tgz.enc من التنزيلات ومن Drive بعد التأكد.
  ⚠ لا تشغّل الطوارئ من الهاتفين معاً؛ الهاتف القديم يبقى احتياطاً أو يُمسح.
EOF
