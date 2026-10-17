#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  إعادة بناء أنظمة الطوارئ على الهاتف (Termux) بأمر واحد
#  يصلح بعد: إعادة ضبط المصنع، أو الانتقال إلى هاتف جديد.
#
#  قبل تشغيله ثبّت من F-Droid هذه التطبيقات (مرة واحدة):
#     Termux · Termux:Widget · Termux:API · Termux:Boot
#
#  ثم في Termux نفّذ سطراً واحداً:
#     pkg install -y git && \
#     git clone https://github.com/AcsVe/IAJ ~/iaj 2>/dev/null; \
#     bash ~/iaj/standby/restore.sh
#  (سيطلب رمز GitHub مرة واحدة إن لم يكن محفوظاً)
# ================================================================
set -u
GH_TOKEN_FILE="$HOME/.iaj_github_token"
SYSTEMS="iaj:IAJ attendance:Attendance rastkt:RASTKT venues:venues"   # مجلد:اسم‑المستودع

c()  { printf '\n\033[1;36m» %s\033[0m\n' "$*"; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
wn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }

# ---------- 1) الرمز ----------
TK="${1:-}"
[ -z "$TK" ] && [ -s "$GH_TOKEN_FILE" ] && TK="$(cat "$GH_TOKEN_FILE")"
if [ -z "$TK" ]; then
  printf '  الصق رمز GitHub (Fine-grained · Contents: Read) ثم Enter: '
  read -r TK
fi
[ -z "$TK" ] && { wn "لا يمكن المتابعة بدون رمز GitHub."; exit 1; }
printf '%s' "$TK" > "$GH_TOKEN_FILE"; chmod 600 "$GH_TOKEN_FILE"

# ---------- 2) المتطلبات الأساسية ----------
c "تثبيت الأدوات الأساسية (git · python · rclone · cloudflared)"
pkg install -y git python rclone cloudflared unzip termux-api >/dev/null 2>&1 \
  || pkg install -y git python rclone cloudflared unzip termux-api
termux-setup-storage 2>/dev/null || true

# ---------- 3) جلب الأكواد الأربعة ----------
for pair in $SYSTEMS; do
  d="${pair%%:*}"; repo="${pair##*:}"
  url="https://x-access-token:${TK}@github.com/AcsVe/${repo}.git"
  clean="https://github.com/AcsVe/${repo}.git"
  if [ -d "$HOME/$d/.git" ]; then
    c "تحديث $d"
    git -C "$HOME/$d" remote set-url origin "$url"
    git -C "$HOME/$d" fetch -q origin main && git -C "$HOME/$d" reset -q --hard origin/main && ok "$d محدَّث" || wn "تعذّر تحديث $d"
  else
    c "تنزيل $d"
    git clone -q "$url" "$HOME/$d" && ok "$d جاهز" || { wn "تعذّر تنزيل $d — تحقّق أن الرمز يشمل مستودع $repo"; continue; }
  fi
  git -C "$HOME/$d" remote set-url origin "$clean"   # لا نُبقي الرمز داخل إعدادات git
done

# ---------- 4) إعداد كل نظام (IAJ أولاً فهو مصدر الرموز المشتركة) ----------
for pair in $SYSTEMS; do
  d="${pair%%:*}"
  [ -f "$HOME/$d/standby/phone.sh" ] || { wn "تخطّي $d (لا يوجد phone.sh)"; continue; }
  c "تثبيت متطلبات $d (قد يستغرق دقائق في أول مرة)"
  bash "$HOME/$d/standby/phone.sh" setup || wn "setup لـ $d أبلغ عن تنبيه"
  c "ضبط رموز وأزرار $d"
  bash "$HOME/$d/standby/phone.sh" configure || wn "configure لـ $d أبلغ عن تنبيه"
done

# ---------- 5) ربط Google Drive (مرة واحدة) ----------
if rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
  ok "Google Drive مربوط مسبقاً (gdrive)"
else
  wn "Google Drive غير مربوط — النسخ الاحتياطي والاسترجاع يحتاجانه."
  printf '  هل تريد ربطه الآن؟ (y/n): '; read -r ans
  if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    echo "   اختر: n (new) ← الاسم: gdrive ← النوع: drive ← scope: 1 ← ثم اتبع رابط تسجيل الدخول"
    rclone config
  else
    echo "   لربطه لاحقاً:  rclone config   (الاسم: gdrive · النوع: drive)"
  fi
fi

c "تم إعادة البناء."
echo "   • حدّث أداة Termux:Widget على الشاشة الرئيسية لتظهر أزرار IAJ / ATT / غيرها."
echo "   • للتأكد أين يعمل كل نظام:  bash ~/iaj/standby/phone.sh status"
echo "   • الطوارئ: زر «IAJ 1» للجائزة، «ATT 1» للحضور، وهكذا."
