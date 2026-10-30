#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  فحص الهاتف الاحتياطي: هل كل شيء جاهز للطوارئ؟ (لا يغيّر شيئاً — قراءة فقط)
#
#   bash ~/iaj/standby/doctor.sh        (أو زر «★ فحص جاهزية الهاتف»، أو اللوحة ← d)
#
#  يفحص: أدوات Termux، الوصول إلى ملفات الهاتف، Google Drive وعمر آخر نسخة لكل نظام، رمز Cloudflare،
#  ولكل نظام: الكود، مكتبات Python، ملف الإعدادات، رمز نفق الهاتف، البريد، والموقع العام — ثم الأزرار.
#  ✓ سليم · ! يعمل مع ملاحظة · ✗ يجب إصلاحه (مع طريقة الإصلاح)
# ================================================================
. "$HOME/iaj/standby/systems.sh"
[ -f "$HOME/.iaj_standby" ] && . "$HOME/.iaj_standby"
REMOTE="${REMOTE:-gdrive:IAJ-backups}"
LANG_UI="${LANG_UI:-ar}"
T() { if [ "$LANG_UI" = "en" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }
G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; C='\033[1;36m'; D='\033[2m'; O='\033[0m'
NOK=0; NWARN=0; NBAD=0
ok()   { NOK=$((NOK + 1));   printf "  ${G}✓${O} %s\n" "$1"; }
warn() { NWARN=$((NWARN + 1)); printf "  ${Y}!${O} %s\n" "$1"; [ -n "$2" ] && printf "    ${D}→ %s${O}\n" "$2"; return 0; }
bad()  { NBAD=$((NBAD + 1)); printf "  ${R}✗${O} %s\n" "$1"; [ -n "$2" ] && printf "    ${D}→ %s${O}\n" "$2"; return 0; }
head_() { printf "\n${C}%b${O}\n" "$1"; }

# ---------------------------------------------------------------- the phone
head_ "$(T "الهاتف وTermux" "Phone and Termux")"
for c in python rclone cloudflared curl unzip; do
  if command -v "$c" >/dev/null 2>&1; then ok "$c"; else bad "$c $(T "غير مثبّت" "missing")" "pkg install -y $c"; fi
done
[ -d "$HOME/storage/shared" ] && ok "$(T "الوصول إلى ملفات الهاتف" "Access to the phone's files")" \
  || warn "$(T "لا وصول إلى ملفات الهاتف" "No access to the phone's files")" "termux-setup-storage"
command -v termux-notification >/dev/null 2>&1 && ok "Termux:API" \
  || warn "$(T "Termux:API غير مثبّت (إشعارات المراقبة لا تعمل)" "Termux:API missing (monitoring notifications off)")" "F-Droid: Termux:API + pkg install termux-api"
if command -v termux-wake-lock >/dev/null 2>&1; then ok "$(T "منع النوم أثناء الطوارئ" "Wake lock for emergency mode")"; fi

# ---------------------------------------------------------------- Google Drive
head_ "Google Drive"
DRIVE=0
if ! rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
  bad "$(T "لا يوجد اتصال باسم gdrive" "No rclone remote named gdrive")" "rclone config  ($(T "الاسم" "name"): gdrive, storage: drive)"
elif ! timeout 60 rclone lsd "$REMOTE" --retries 1 --low-level-retries 2 >/dev/null 2>&1; then
  ERR="$(timeout 60 rclone lsd gdrive: --retries 1 --low-level-retries 1 2>&1 | tail -1 | cut -c1-160)"
  if timeout 60 rclone lsd gdrive: --retries 1 --low-level-retries 1 >/dev/null 2>&1; then
    bad "$(T "الاتصال يعمل لكن المجلد غير موجود:" "Drive works but the folder is missing:") ${REMOTE#gdrive:}" \
        "$(T "سجّل الدخول بحساب Google الذي يحفظ فيه الكمبيوتر النسخ: rclone config ← gdrive ← Edit" "Sign in with the Google account the PC backs up to: rclone config > gdrive > Edit")"
  else
    bad "$(T "تعذّر فتح Google Drive" "Google Drive cannot be opened")" "$ERR"
    printf "    ${D}→ %s${O}\n" "$(T "أعد ربطه: rclone config reconnect gdrive:" "Reconnect: rclone config reconnect gdrive:")"
  fi
else
  DRIVE=1; ok "$(T "Google Drive متصل:" "Google Drive connected:") ${REMOTE#gdrive:}"
fi

backup_age() {   # minutes since the newest *.gz in a Drive folder (computer backups, not the phone's)
  rclone lsl "$1" --include "*.gz" --exclude "*-phone.*" --max-depth 1 2>/dev/null | sort -k2,3 | tail -1 | python -c "
import sys, datetime
p = sys.stdin.read().split()
if len(p) < 3: print('?'); sys.exit()
t = datetime.datetime.strptime(p[1] + ' ' + p[2][:8], '%Y-%m-%d %H:%M:%S')
print(int((datetime.datetime.now() - t).total_seconds() // 60))"
}

# ---------------------------------------------------------------- Cloudflare
head_ "Cloudflare"
CF="$(grep -h '^CF_API_TOKEN=' "$HOME/iaj/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
if [ -z "$CF" ]; then
  bad "$(T "لا يوجد رمز Cloudflare على الهاتف" "No Cloudflare token on the phone")" "$(T "أعد تشغيل المثبّت" "Run the installer again")"
elif CF_API_TOKEN="$CF" python - <<'PY'
import json, os, sys, urllib.request
r = urllib.request.Request('https://api.cloudflare.com/client/v4/zones?name=iajaward.org',
                           headers={'Authorization': 'Bearer ' + os.environ['CF_API_TOKEN']})
try:
    sys.exit(0 if json.load(urllib.request.urlopen(r, timeout=30)).get('result') else 1)
except Exception:
    sys.exit(1)
PY
then ok "$(T "رمز Cloudflare مقبول" "Cloudflare token accepted")"
else bad "$(T "Cloudflare رفض الرمز أو لا إنترنت" "Cloudflare refused the token, or no internet")" "$(T "أعد تشغيل المثبّت وألصق الرمز من C:\\IAJ\\.env" "Run the installer and paste the token from C:\\IAJ\\.env")"
fi

# ---------------------------------------------------------------- each system
missing_libs() {   # the Python libraries of the system that are not installed (versions are not compared)
  python - "$1" <<'PY'
import re, sys, os
from importlib import metadata
site = sys.argv[1]
req = os.path.join(site, 'standby', 'requirements-phone.txt')
if not os.path.isfile(req):
    req = os.path.join(site, 'requirements.txt')
SKIP = {'gunicorn', 'psycopg', 'psycopg2', 'psycopg2-binary', 'pyodbc', 'pywin32', 'pyinstaller'}
OPTIONAL = {'pywebpush', 'py-vapid', 'flask-compress'}   # the phone setup installs these only if it can
out = []
for line in open(req, encoding='utf-8-sig') if os.path.isfile(req) else []:
    line = line.split('#')[0].strip()
    if not line or line.startswith('-'):
        continue
    if ';' in line and 'win32' in line.split(';', 1)[1] and '!=' not in line.split(';', 1)[1]:
        continue
    name = re.split(r'[\s\[<>=!~;]', line, 1)[0]
    if name.lower() in SKIP:
        continue
    try:
        metadata.version(name)
    except metadata.PackageNotFoundError:
        out.append(('?' if name.lower() in OPTIONAL else '') + name)
print(' '.join(out))
PY
}
http_code() { local c; c="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$1/" 2>/dev/null)"; echo "${c:-000}"; }

while IFS='|' read -r d code ar en url <&3; do   # (fd 3: the checks below must not read the list)
  name="$(T "$ar" "$en")"
  head_ "$code · $name  ${D}${url#https://}${O}"
  if [ ! -f "$HOME/$d/standby/phone.sh" ]; then
    warn "$(T "غير مثبّت على الهاتف" "Not installed on the phone")" "$(T "المثبّت ← اختر هذا النظام" "Installer > choose this system")"
    continue
  fi
  if [ -f "$HOME/$d/serve.py" ]; then ok "$(T "الكود موجود" "Code present")"
  else bad "$(T "الكود ناقص" "Code incomplete")" "bash ~/$d/standby/phone.sh update-code"; fi

  miss="$(missing_libs "$HOME/$d" 2>/dev/null)"
  need="$(printf '%s\n' $miss | grep -v '^?' | tr '\n' ' ')"; opt="$(printf '%s\n' $miss | grep '^?' | tr -d '?' | tr '\n' ' ')"
  if [ -z "${need// }" ]; then ok "$(T "مكتبات Python كاملة" "Python libraries complete")"
  else bad "$(T "مكتبات ناقصة:" "Missing libraries:") $need" "bash ~/$d/standby/phone.sh setup"; fi
  [ -z "${opt// }" ] || warn "$(T "مكتبات اختيارية غير مثبّتة:" "Optional libraries not installed:") $opt" "$(T "إشعارات المتصفح أو الضغط فقط — يعمل النظام بدونها" "Browser notifications or compression only - the system works without them")"
  [ "$d" = timetable ] && { command -v pg_ctl >/dev/null 2>&1 && ok "PostgreSQL" || bad "$(T "PostgreSQL غير مثبّت" "PostgreSQL missing")" "bash ~/timetable/standby/phone.sh setup"; }

  envf="$HOME/$d/.env"; [ -f "$HOME/$d/config.env" ] && envf="$HOME/$d/config.env"
  if [ -f "$envf" ]; then ok "$(T "ملف الإعدادات" "Settings file") ($(basename "$envf"))"
  else bad "$(T "لا يوجد ملف إعدادات" "No settings file")" "bash ~/$d/standby/phone.sh configure"; fi

  tk="$HOME/.${d}_tunnel_token"
  if [ -s "$tk" ]; then ok "$(T "رمز نفق الهاتف" "Phone tunnel token") (${d}-standby)"
  else bad "$(T "لا يوجد رمز نفق الهاتف — الطوارئ لن تعمل" "No phone tunnel token - emergency mode will not work")" "bash ~/$d/standby/phone.sh configure"; fi

  if grep -qE '^(MS_CLIENT_SECRET|EMAIL_HOST_PASSWORD)=.' "$envf" 2>/dev/null; then ok "$(T "إعدادات البريد" "Email settings")"
  else warn "$(T "بلا إعدادات بريد (لن يُرسل بريد من الهاتف)" "No email settings (no email from the phone)")" "$(T "الكمبيوتر: phone_mail.bat ← الهاتف: اللوحة ← m" "PC: phone_mail.bat > phone: panel > m")"; fi

  if [ "$DRIVE" = 1 ]; then
    if [ "$d" = iaj ]; then folder="$REMOTE/db"; else folder="$REMOTE/$d/db"; fi
    age="$(backup_age "$folder")"
    if [ "$age" = "?" ] || [ -z "$age" ]; then bad "$(T "لا نسخ احتياطية في Drive" "No backups in Drive")" "${folder#gdrive:}"
    elif [ "$age" -le 180 ]; then ok "$(T "آخر نسخة من الكمبيوتر قبل" "Last PC backup") $age $(T "دقيقة" "min")"
    else warn "$(T "آخر نسخة من الكمبيوتر قديمة:" "Last PC backup is old:") $((age / 60)) $(T "ساعة" "h")" "$(T "تحقّق من مهمة النسخ على الكمبيوتر" "Check the backup task on the PC")"; fi
  fi

  hc="$(http_code "$url")"
  if pgrep -f "$d/standby/phone.sh (takeover|start)" >/dev/null 2>&1; then warn "$(T "يعمل من الهاتف الآن (طوارئ)" "Served by this phone now (emergency)")"; fi
  case "$hc" in
    2??|3??) ok "$(T "الموقع العام يعمل" "Public site up") ($hc)" ;;
    530|52?|502) warn "$(T "الموقع العام متوقف: الكمبيوتر أو نفقه في Cloudflare غير متصل" "Public site down: the PC or its Cloudflare tunnel is not connected") ($hc)" \
         "$(T "تحقّق من الكمبيوتر (site_where.bat)، أو زر النظام ← تشغيل الطوارئ" "Check the PC (site_where.bat), or system button > Emergency")" ;;
    *) warn "$(T "الموقع العام لا يفتح" "Public site not reachable") ($hc)" "$(T "إن كان الكمبيوتر متوقفاً: زر النظام ← تشغيل الطوارئ" "If the PC is down: system button > Emergency")" ;;
  esac
done 3<<< "$IAJ_SYSTEMS"

# ---------------------------------------------------------------- buttons
head_ "Termux:Widget"
n=$(ls "$HOME/.shortcuts" 2>/dev/null | grep -c '')
old=$(ls "$HOME/.shortcuts" 2>/dev/null | grep -cE '^(IAJ|TKT|VEN|ATT|TT|BELL|CLR|SAS) [0-9N]')
if [ -x "$HOME/.shortcuts/★ لوحة الأنظمة" ]; then ok "$(T "الأزرار جاهزة:" "Buttons ready:") $n"
else bad "$(T "زر لوحة الأنظمة غير موجود" "Systems panel button missing")" "bash ~/iaj/standby/widgets.sh"; fi
[ "$old" = 0 ] || warn "$(T "أزرار قديمة متبقية:" "Old buttons left:") $old" "bash ~/iaj/standby/widgets.sh"
if pm list packages 2>/dev/null | grep -q 'com.termux.widget'; then ok "$(T "تطبيق Termux:Widget مثبّت" "Termux:Widget app installed")"; fi
[ -f "$HOME/.iaj_lock" ] && ok "$(T "الإجراءات الحساسة مقفلة (افتحها عند الطوارئ)" "Sensitive actions locked (unlock in an emergency)")" \
  || warn "$(T "الإجراءات الحساسة مفتوحة" "Sensitive actions are unlocked")" "$(T "زر «★ قفل أو فتح الأزرار»" "button «★ قفل أو فتح الأزرار»")"

# ---------------------------------------------------------------- result
printf "\n${C}%s${O}  ${G}✓ %d${O}   ${Y}! %d${O}   ${R}✗ %d${O}\n" "$(T "النتيجة" "Result")" "$NOK" "$NWARN" "$NBAD"
if [ "$NBAD" = 0 ]; then printf "  ${G}%s${O}\n" "$(T "الهاتف جاهز للطوارئ." "The phone is ready for emergency mode.")"
else printf "  ${R}%s${O}\n" "$(T "أصلح البنود المعلّمة ✗ ثم أعد الفحص." "Fix the ✗ items, then check again.")"; fi
[ "$NBAD" = 0 ]
