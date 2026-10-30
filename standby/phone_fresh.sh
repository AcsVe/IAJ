#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  NEW PHONE FROM SCRATCH - when the old phone is lost or broken
#  (no backup file from the old phone is needed: the code comes from GitHub,
#   the data from Google Drive, the tunnels from Cloudflare)
#
#  Rebuilds the standby of every iajaward.org system on this phone:
#    iaj (award site), rastkt (1), venues (2), attendance (3), timetable (4),
#    bell (5), clearance (6), sas (8) - and the Termux:Widget buttons (standby/widgets.sh):
#    a systems panel, update-all, lock, language and one button per system.
#
#  Before: install Termux and Termux:Widget (and Termux:API) from the SAME source -
#  F-Droid or GitHub, not the Play Store. Then in Termux:
#
#    curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_fresh.sh | bash
#
#  You need: the Cloudflare API token (the same one as on the PC: CF_API_TOKEN in C:\IAJ\.env)
#  and the school Google account (for Google Drive). A GitHub token is optional.
#  Safe to run again: finished systems are only updated, their settings and data are kept.
#  (English messages: Termux does not join or right-to-left Arabic)
# ================================================================
set -u
say()  { printf '\n\033[1;36m> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mX %s\033[0m\n' "$*"; exit 1; }
TTY="${FRESH_TTY:-/dev/tty}"

# dir | GitHub repo | name
SYSTEMS="iaj|IAJ|Award site (iajaward.org)
rastkt|RASTKT|Tickets (1.iajaward.org)
venues|venues|Venues (2.iajaward.org)
attendance|Attendance|Attendance (3.iajaward.org)
timetable|Timetable|Timetable (4.iajaward.org)
bell|Bell|Bell (5.iajaward.org)
clearance|Clearance|Clearance (6.iajaward.org)
sas|sas|Student absence (8.iajaward.org)"

CF_API="${CF_API:-https://api.cloudflare.com/client/v4}"; export CF_API

main() {
[ -d /data/data/com.termux ] || [ -n "${FRESH_TEST:-}" ] || die "Run this inside Termux on the phone."
exec 3< "$TTY" || die "No keyboard input (run it in the Termux window)"   # answers come from the keyboard, not the curl pipe

# ---------------------------------------------------------------- 1) Termux
say "1) Preparing Termux (several minutes the first time)"
# never stop at dpkg's «configuration file changed» question (there is no keyboard behind the curl pipe):
# keep the file already on the phone, and finish any package an earlier run left half-installed
export DEBIAN_FRONTEND=noninteractive
APT_Y="-y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
fix_dpkg() { dpkg --force-confdef --force-confold --configure -a < /dev/null >/dev/null 2>&1 || true
             apt-get $APT_Y -f install < /dev/null >/dev/null 2>&1 || true; }
PKGS="python rclone cloudflared unzip curl openssl-tool ca-certificates"
fix_dpkg
apt-get update < /dev/null >/dev/null 2>&1 || pkg update -y < /dev/null >/dev/null 2>&1 || true
apt-get $APT_Y install $PKGS termux-api < /dev/null >/dev/null 2>&1 \
  || { fix_dpkg; apt-get $APT_Y install $PKGS < /dev/null; } \
  || die "Installing the Termux packages failed - check the internet and run the same command again"
if [ ! -d "$HOME/storage/shared" ]; then
  echo "  Allow Termux to access the phone's files (a window will appear)..."
  termux-setup-storage || true; sleep 5
fi

# ---------------------------------------------------------------- 2) which systems
say "2) Systems to install"
i=0
while IFS='|' read -r d r n; do
  mark=""; [ -f "$HOME/$d/standby/phone.sh" ] && mark="   (already on this phone - will be updated)"
  printf '   %d  %s%s\n' "$i" "$n" "$mark"; i=$((i + 1))
done <<< "$SYSTEMS"
read -r -p "  Enter = all, or the numbers separated by spaces (e.g.  0 1 4): " PICK <&3
case "$(printf '%s' "$PICK" | tr -d '[:space:]' | tr 'A-Z' 'a-z')" in all|a|\*|كل|الكل) PICK="" ;; esac
CHOSEN=""
i=0
while IFS='|' read -r d r n; do
  if [ -z "$PICK" ] || [ "$i" = 0 ] || printf ' %s ' "$PICK" | grep -q " $i "; then CHOSEN="$CHOSEN $d"; fi
  i=$((i + 1))
done <<< "$SYSTEMS"
echo "  Installing:$CHOSEN   (the award site is always included: the others take the Cloudflare token and the lock/language buttons from it)"

# ---------------------------------------------------------------- 3) tokens
say "3) Tokens (nothing shows while you paste - long-press > Paste, then Enter)"
CF="$(grep -h '^CF_API_TOKEN=' "$HOME/iaj/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
cf_check() {
  CF_API_TOKEN="$1" python - <<'PY'
import json, os, sys, urllib.request
req = urllib.request.Request(os.environ['CF_API'] + '/zones?name=iajaward.org',
                             headers={'Authorization': 'Bearer ' + os.environ['CF_API_TOKEN']})
try:
    ok = json.load(urllib.request.urlopen(req, timeout=30)).get('result')
except Exception:
    ok = None
sys.exit(0 if ok else 1)
PY
}
for attempt in 1 2 3; do
  if [ -n "$CF" ] && cf_check "$CF"; then echo "  Cloudflare token: OK"; break; fi
  [ -n "$CF" ] && warn "Cloudflare refused this token"
  read -r -s -p "  Cloudflare API token (CF_API_TOKEN from C:\\IAJ\\.env on the PC): " CF <&3; echo
  CF="$(printf '%s' "$CF" | tr -d '[:space:]')"
done
cf_check "$CF" || die "No working Cloudflare token - without it the phone cannot take over the sites. Run again when you have it."

if [ ! -s "$HOME/.iaj_github_token" ] && [ ! -f "$HOME/.iaj_github_skip" ]; then   # asked once
  read -r -s -p "  (optional) GitHub read-only token - or Enter to skip: " GH <&3; echo
  GH="$(printf '%s' "$GH" | tr -d '[:space:]')"
  if [ -n "$GH" ]; then printf '%s' "$GH" > "$HOME/.iaj_github_token"; chmod 600 "$HOME/.iaj_github_token"; rm -f "$HOME/.iaj_github_skip"
  else touch "$HOME/.iaj_github_skip"; echo "  Skipped: code updates will come from Google Drive (the PC puts a copy there every hour)."; fi
fi

# ---------------------------------------------------------------- 4) Google Drive
say "4) Google Drive"
if ! rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
  echo "  Connect Google Drive. Answer:   n  >  name: gdrive  >  storage: drive  >  Enter for the rest,"
  echo "  'Use web browser to authenticate' = y, sign in with the SCHOOL Google account, then q to quit."
  rclone config <&3
fi
if rclone lsd gdrive:IAJ-backups >/dev/null 2>&1; then
  echo "  Google Drive: OK ($(rclone lsd gdrive:IAJ-backups 2>/dev/null | wc -l) system folders in IAJ-backups)"
else
  warn "Cannot read gdrive:IAJ-backups - the systems install, but emergency mode needs Drive. Fix later with: rclone config"
fi

# ---------------------------------------------------------------- 5) each system
download() {   # $1 dir, $2 repo
  local tmp; tmp="$(mktemp -d)"
  if [ -s "$HOME/.iaj_github_token" ]; then
    curl -fsSL -H "Authorization: Bearer $(cat "$HOME/.iaj_github_token")" \
      "https://api.github.com/repos/AcsVe/$2/zipball/main" -o "$tmp/c.zip" 2>/dev/null \
      || curl -fsSL "https://codeload.github.com/AcsVe/$2/zip/refs/heads/main" -o "$tmp/c.zip" || { rm -rf "$tmp"; return 1; }
  else
    curl -fsSL "https://codeload.github.com/AcsVe/$2/zip/refs/heads/main" -o "$tmp/c.zip" || { rm -rf "$tmp"; return 1; }
  fi
  unzip -q "$tmp/c.zip" -d "$tmp/x" || { rm -rf "$tmp"; return 1; }
  mkdir -p "$HOME/$1"
  # merge: only files from GitHub are written; settings, data and backups already on the phone stay
  (cd "$tmp/x"/*/ && tar -cf - --exclude=./.env --exclude=./config.env . ) | (cd "$HOME/$1" && tar -xf -)
  sed -i 's/\r$//' "$HOME/$1"/standby/*.sh 2>/dev/null || true
  if [ -n "${FRESH_TEST:-}" ]; then   # test runs only: a stand-in Cloudflare API
    sed -i "s#https://api.cloudflare.com/client/v4#$CF_API#" "$HOME/$1"/ops/cf.py "$HOME/$1"/standby/cf_switch.py 2>/dev/null || true
  fi
  rm -rf "$tmp"
}

iaj_tunnel_token() {   # the award site asks for its phone tunnel token by hand; fetch it from Cloudflare instead
  [ -s "$HOME/.iaj_tunnel_token" ] && return 0
  CF_API_TOKEN="$CF" python - "$HOME/.iaj_tunnel_token" <<'PY' && chmod 600 "$HOME/.iaj_tunnel_token"
import json, os, sys, urllib.request
H = {'Authorization': 'Bearer ' + os.environ['CF_API_TOKEN']}
api = lambda p: json.load(urllib.request.urlopen(urllib.request.Request(os.environ['CF_API'] + p, headers=H), timeout=30))['result']
acc = api('/zones?name=iajaward.org')[0]['account']['id']
tun = api(f'/accounts/{acc}/cfd_tunnel?name=iaj-standby&is_deleted=false')
if not tun:
    sys.exit(1)
open(sys.argv[1], 'w').write(api(f"/accounts/{acc}/cfd_tunnel/{tun[0]['id']}/token"))
PY
}

blanks() { for _ in $(seq 1 25); do echo; done; }   # Enter for every optional question (email, Neon)

SUMMARY=""
for d in $CHOSEN; do
  line="$(printf '%s\n' "$SYSTEMS" | grep "^$d|")"
  repo="$(echo "$line" | cut -d'|' -f2)"; name="$(echo "$line" | cut -d'|' -f3)"
  say "5) $name - ~/$d"
  if ! download "$d" "$repo"; then
    [ "$d" = iaj ] && die "Could not download the award site (AcsVe/IAJ) - the other systems need it. Check the internet and run again."
    warn "could not download AcsVe/$repo"; SUMMARY="$SUMMARY\n  X  $name: download failed"; continue
  fi
  echo "  code downloaded"
  log="$HOME/fresh-$d.log"
  echo "  installing (may take several minutes; details in $log)..."
  bash "$HOME/$d/standby/phone.sh" setup <&3 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  [ "$rc" = 0 ] || warn "setup ended with an error (code $rc) - see $log; continuing"
  send_cf=0
  if [ "$d" = iaj ]; then
    iaj_tunnel_token || warn "phone tunnel iaj-standby not found in Cloudflare - the award site will ask for it"
    grep -q '^CF_API_TOKEN=.' "$HOME/iaj/.env" 2>/dev/null || send_cf=1
  fi
  # the answers go straight into the pipe (a $(...) would drop the empty lines)
  if { [ "$send_cf" = 1 ] && printf '%s\n' "$CF"; blanks; } | bash "$HOME/$d/standby/phone.sh" configure >> "$log" 2>&1; then
    SUMMARY="$SUMMARY\n  OK $name"
  else
    if [ "$d" = sas ] && grep -q 'standby' "$log"; then   # SAS not installed on the PC yet: its tunnel does not exist
      SUMMARY="$SUMMARY\n  !  $name: not set up on the PC yet - to start it on this phone run: bash ~/sas/standby/phone.sh first"
    else
      SUMMARY="$SUMMARY\n  !  $name: configure did not finish - run: bash ~/$d/standby/phone.sh configure"
    fi
    tail -3 "$log" | sed 's/^/     /'
  fi
done

# ---------------------------------------------------------------- email settings (prepared on the PC)
MAIL_DONE=0
if rclone lsf gdrive:IAJ-backups/phone/mail-settings.enc >/dev/null 2>&1 && \
   [ -n "$(rclone lsf gdrive:IAJ-backups/phone/mail-settings.enc 2>/dev/null)" ]; then
  say "Email settings of every system (file made on the PC by phone_mail.bat)"
  read -r -p "  Copy them to this phone now? [Y/n] " A <&3
  case "$A" in n|N) ;; *) REMOTE=gdrive:IAJ-backups bash "$HOME/iaj/standby/panel.sh" mail <&3 && MAIL_DONE=1 ;; esac
fi

# ---------------------------------------------------------------- 6) done
say "Checking that everything is ready (standby/doctor.sh)"
LANG_UI=en bash "$HOME/iaj/standby/doctor.sh" < /dev/null || true

say "6) Result"
printf '%b\n' "$SUMMARY"
echo
WIDGETS_QUIET=1 bash "$HOME/iaj/standby/widgets.sh" 2>/dev/null || true
echo "  Termux:Widget buttons: '★ لوحة الأنظمة' (all sites at a glance), '★ تحديث كل الأنظمة', lock, language,"
echo "  and one button per system (IAJ, TKT, VEN, ATT, TT, BELL, CLR, SAS) that opens its actions."
echo "  Next:"
echo "   - Add the Termux:Widget to the home screen (long-press the home screen > Widgets > Termux:Widget),"
echo "     or refresh it if it is already there."
echo "   - Sensitive actions start LOCKED: press '★ قفل أو فتح الأزرار' to unlock before an emergency."
if [ "${MAIL_DONE:-0}" = 1 ]; then echo "   - Email settings: copied from the PC for every system."
else echo "   - Email: on the PC run C:\\IAJ\\phone_mail.bat once, then on the phone: '★ لوحة الأنظمة' > m"; fi
echo "   - Where each site runs: '★ لوحة الأنظمة'."
}

main "$@"
