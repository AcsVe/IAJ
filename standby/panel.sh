#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  لوحة الأنظمة على الهاتف (Termux) — تفتحها أزرار Termux:Widget (widgets.sh)
#
#   bash ~/iaj/standby/panel.sh              # حالة كل المواقع + اختيار نظام
#   bash ~/iaj/standby/panel.sh venues       # قائمة نظام واحد: حالته الآن وإجراءاته
#   bash ~/iaj/standby/panel.sh update-all   # تحديث كود كل الأنظمة المثبّتة على الهاتف
#   bash ~/iaj/standby/panel.sh mail         # إعدادات البريد لكل نظام من الكمبيوتر (phone_mail.bat في مجلد موقع الجائزة على الكمبيوتر)
#
#  الإجراءات نفسها في standby/phone.sh لكل نظام (القفل يحمي الحساسة منها كما في السابق).
# ================================================================
. "$HOME/iaj/standby/systems.sh"
[ -f "$HOME/.iaj_standby" ] && . "$HOME/.iaj_standby"
LANG_UI="${LANG_UI:-en}"   # Termux cannot join or right-to-left Arabic: English unless chosen
export IAJ_LANG="$LANG_UI" PYTHONUTF8=1
T() { if [ "$LANG_UI" = "en" ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }
say() { printf '\n\033[1;36m» %s\033[0m\n' "$*"; }
GREEN='\033[1;32m'; RED='\033[1;31m'; YEL='\033[1;33m'; DIM='\033[2m'; OFF='\033[0m'

field() {   # field <folder> <n>  (2 code, 3 Arabic, 4 English, 5 address)
  printf '%s\n' "$IAJ_SYSTEMS" | grep "^$1|" | cut -d'|' -f"$2"
}
name() { if [ "$LANG_UI" = "en" ]; then field "$1" 4; else field "$1" 3; fi; }
installed() { [ -f "$HOME/$1/standby/phone.sh" ]; }
on_phone() { pgrep -f "$1/standby/phone.sh (takeover|start)" >/dev/null 2>&1; }
probe() {   # probe <url> <file>: «code seconds» (000 = did not open)
  curl -s -o /dev/null -m 12 -w '%{http_code} %{time_total}' "$1/" > "$2" 2>/dev/null || echo "000 0" > "$2"
}
state_line() {   # state_line <folder> <probe file>
  local code secs
  read -r code secs < "$2" 2>/dev/null
  case "$code" in
    2??|3??) printf "${GREEN}%s${OFF} ${DIM}(%.1fs)${OFF}" "$(T "يعمل" "up")" "${secs:-0}" ;;
    000|'')  printf "${RED}%s${OFF}" "$(T "لا يفتح" "unreachable")" ;;
    *)       printf "${RED}%s %s${OFF}" "$(T "خطأ" "error")" "$code" ;;
  esac
  on_phone "$1" && printf "  ${YEL}%s${OFF}" "$(T "• يعمل من الهاتف الآن" "• served by this phone now")"
  return 0
}
locked_note() {
  [ -f "$HOME/.iaj_lock" ] && printf "${DIM}  %s${OFF}\n" "$(T "🔒 الإجراءات الحساسة مقفلة — زر «★ قفل أو فتح الأزرار»" "🔒 Sensitive actions are locked - use «★ قفل أو فتح الأزرار»")"
  return 0
}

# ---------------------------------------------------------------- one system
actions() {   # the actions this system's phone.sh offers, in a fixed order
  local f="$HOME/$1/standby/phone.sh" a
  for a in takeover stop server status update backup neon check monitor try; do
    case "$a" in
      update) grep -qE '^  update-code\)' "$f" && echo update ;;
      takeover) grep -qE '^  takeover(\|start)?\)' "$f" && echo takeover ;;
      *) grep -qE "^  $a\)" "$f" && echo "$a" ;;
    esac
  done
}
label() {
  case "$1" in
    takeover) T "تشغيل الطوارئ: تحويل العنوان إلى الهاتف" "Emergency: serve the address from this phone" ;;
    stop)     T "إنهاء الطوارئ" "End emergency mode" ;;
    server)   T "إرجاع العنوان إلى الكمبيوتر (دون نقل بيانات)" "Point the address back to the PC (no data moved)" ;;
    status)   T "أين يعمل الآن (تفصيل من Cloudflare)" "Where it runs now (Cloudflare details)" ;;
    update)   T "تحديث الكود على الهاتف" "Update the code on the phone" ;;
    backup)   T "نسخ بيانات الهاتف إلى Drive" "Copy the phone data to Drive" ;;
    neon)     T "استرجاع أحدث نسخة من Neon إلى الهاتف" "Restore the latest Neon copy onto the phone" ;;
    check)    T "فحص سريع للموقع وآخر نسخة احتياطية" "Quick check of the site and the last backup" ;;
    monitor)  T "المراقبة: إشعار عند توقف الموقع (تشغيل أو إيقاف)" "Monitoring: notify when the site goes down (on/off)" ;;
    try)      T "تجربة على الهاتف فقط (دون تحويل العنوان)" "Try on the phone only (address not switched)" ;;
  esac
}
run_action() {   # run_action <folder> <action>
  local f="$HOME/$1/standby/phone.sh"
  case "$2" in
    update) bash "$f" update-code && bash "$f" configure ;;
    *)      bash "$f" "$2" ;;
  esac
}
system_menu() {
  local d="$1" url tmp acts i a pick
  installed "$d" || { say "$(T "هذا النظام غير مثبّت على الهاتف" "This system is not installed on the phone")"; return 1; }
  url="$(field "$d" 5)"; tmp="$(mktemp)"
  printf '\n\033[1;36m%s · %s\033[0m  %s\n' "$(field "$d" 2)" "$(name "$d")" "${url#https://}"
  printf '  %s ' "$(T "جارٍ الفحص…" "checking...")"; probe "$url" "$tmp"; printf '\r\033[K  '; state_line "$d" "$tmp"; echo
  rm -f "$tmp"; locked_note; echo
  acts="$(actions "$d")"; i=0
  for a in $acts; do i=$((i + 1)); printf '  %2d  %s\n' "$i" "$(label "$a")"; done
  printf '   0  %s\n\n' "$(T "خروج" "Exit")"
  read -r -p "$(T "  الرقم: " "  Number: ")" pick
  [ -z "$pick" ] || [ "$pick" = 0 ] && return 0
  a="$(printf '%s\n' $acts | sed -n "${pick}p")"
  [ -n "$a" ] || { say "$(T "رقم غير صحيح" "Invalid number")"; return 1; }
  run_action "$d" "$a"
}

# ---------------------------------------------------------------- all systems
overview() {
  local dir list d i pick nm pad
  dir="$(mktemp -d)"; list=""
  while IFS='|' read -r d _; do installed "$d" && list="$list $d"; done <<< "$IAJ_SYSTEMS"
  [ -n "$list" ] || { say "$(T "لا توجد أنظمة مثبّتة على الهاتف" "No systems installed on the phone")"; return 1; }
  printf '\n\033[1;36m%s\033[0m   %s\n' "$(T "لوحة الأنظمة" "Systems panel")" "$(TZ=Asia/Amman date '+%Y-%m-%d %H:%M')"
  printf '  %s ' "$(T "جارٍ فحص المواقع…" "checking the sites...")"
  for d in $list; do probe "$(field "$d" 5)" "$dir/$d" & done; wait
  printf '\r\033[K\n'
  i=0
  for d in $list; do
    i=$((i + 1))
    nm="$(name "$d")"; pad=$((16 - ${#nm})); [ "$pad" -gt 0 ] || pad=1   # by letters, not bytes (Arabic)
    printf '  %d  %-5s %s%*s' "$i" "$(field "$d" 2)" "$nm" "$pad" ''; state_line "$d" "$dir/$d"; echo
  done
  rm -rf "$dir"; echo; locked_note
  printf '  u  %s\n  m  %s\n  d  %s\n  0  %s\n\n' "$(T "تحديث كل الأنظمة" "Update all systems")" "$(T "إعدادات البريد لكل الأنظمة (من الكمبيوتر)" "Email settings of every system (from the PC)")" "$(T "فحص جاهزية الهاتف" "Check the phone is ready")" "$(T "خروج" "Exit")"
  read -r -p "$(T "  رقم النظام لفتح قائمته: " "  System number to open its menu: ")" pick
  case "$pick" in
    ''|0) return 0 ;;
    u|U) update_all; return ;;
    m|M) mail_import; return ;;
    d|D) bash "$HOME/iaj/standby/doctor.sh"; return ;;
  esac
  d="$(printf '%s\n' $list | sed -n "${pick}p")"
  [ -n "$d" ] || { say "$(T "رقم غير صحيح" "Invalid number")"; return 1; }
  system_menu "$d"
}

mail_import() {   # the email settings of every system, prepared on the computer by phone_mail.bat (award site folder)
  local tmp remote="${REMOTE:-gdrive:IAJ-backups}"
  tmp="$(mktemp -d)"
  say "$(T "تنزيل ملف إعدادات البريد من Drive" "Downloading the email settings file from Drive")"
  rclone copy "$remote/phone/mail-settings.enc" "$tmp" 2>/dev/null
  if [ ! -f "$tmp/mail-settings.enc" ]; then
    rm -rf "$tmp"
    say "$(T "لا يوجد الملف بعد — على الكمبيوتر شغّل phone_mail.bat في مجلد موقع الجائزة ثم أعد المحاولة بعد دقيقة" "No file yet - on the PC run phone_mail.bat in the award site folder, then try again a minute later")"
    return 1
  fi
  python "$HOME/iaj/standby/mail_bundle.py" import "$tmp/mail-settings.enc"
  rm -rf "$tmp"
}

update_all() {   # the award site first: it carries this panel and the buttons
  local d ok="" bad="" list=""
  while IFS='|' read -r d _; do installed "$d" && list="$list $d"; done <<< "$IAJ_SYSTEMS"
  for d in $list; do   # (not inside the while: configure may ask questions on the keyboard)
    say "$(field "$d" 2) · $(name "$d")"
    if bash "$HOME/$d/standby/phone.sh" update-code && bash "$HOME/$d/standby/phone.sh" configure; then
      ok="$ok $(field "$d" 2)"
    else
      bad="$bad $(field "$d" 2)"
    fi
  done
  WIDGETS_QUIET=1 bash "$HOME/iaj/standby/widgets.sh"
  say "$(T "تم التحديث:" "Updated:")${ok:- -}"
  [ -z "$bad" ] || printf "${RED}  %s%s${OFF}\n" "$(T "لم يكتمل:" "Not finished:")" "$bad"
  return 0
}

case "${1:-}" in
  '')         overview ;;
  update-all) update_all ;;
  mail)       mail_import ;;
  *)          system_menu "$1" ;;
esac
