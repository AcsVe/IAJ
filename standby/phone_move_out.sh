#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  Move Termux to a new phone - step 1, on the OLD phone
#  (English messages: Termux does not join or right-to-left Arabic)
#
#   curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_out.sh | bash
#
#  Makes ONE password-encrypted file with everything in the home folder: code and data of
#  every system, widget buttons, Termux:Boot, tunnel / GitHub / rclone tokens, .ssh, the
#  pkg / pip / npm lists, enabled services and an SQL copy of the PostgreSQL databases.
#  File: Downloads/termux-move-<date>.tgz.enc   Then on the new phone: phone_move_in.sh
# ================================================================
set -e
say() { printf '\n\033[1;36m> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mX %s\033[0m\n' "$*"; exit 1; }
MOVE="$HOME/.move"
STAMP=$(date +%Y-%m-%d_%H%M)
SKIP_OLD="ars-booking-app helpdesk acs-booking"     # large old folders (ALL=1 to include them)

pgrep -f "standby/phone.sh (takeover|start)" >/dev/null 2>&1 && \
  die "A system is running from this phone now (emergency mode) - stop it first (button '... 1 - stop'), then run this again"

command -v openssl >/dev/null || pkg install -y openssl-tool >/dev/null
[ -d "$HOME/storage/downloads" ] || { termux-setup-storage; sleep 5; }
[ -d "$HOME/storage/downloads" ] || die "No access to Downloads - allow Termux to access files, then run this again"

rm -rf "$MOVE"; mkdir -p "$MOVE"
say "1) Lists of packages, libraries and services"
apt-mark showmanual 2>/dev/null | sort > "$MOVE/pkgs.txt"
pip list --format=freeze 2>/dev/null > "$MOVE/pip.txt" || true
npm ls -g --depth=0 --parseable 2>/dev/null | tail -n +2 | sed 's#.*/node_modules/##' | grep -v '^npm$' > "$MOVE/npm.txt" || true
for s in "$PREFIX"/var/service/*/; do
  n=$(basename "$s"); [ -f "$s/down" ] || echo "$n"
done > "$MOVE/services.txt" 2>/dev/null || true
uname -m > "$MOVE/arch.txt"; date '+%F %T' > "$MOVE/created.txt"
echo "  pkg $(wc -l < "$MOVE/pkgs.txt"), pip $(wc -l < "$MOVE/pip.txt"), npm $(wc -l < "$MOVE/npm.txt"), services $(tr '\n' ' ' < "$MOVE/services.txt")"

say "2) Removing tokens written inside git remote addresses"
for d in "$HOME" "$HOME"/*/; do
  u=$(git -C "$d" remote get-url origin 2>/dev/null) || continue
  case "$u" in https://*@*)
    git -C "$d" remote set-url origin "https://${u#*@}"
    echo "  removed a token from $(basename "$d") - also revoke that token on GitHub" ;;
  esac
done

say "3) SQL copy of the PostgreSQL databases, then stop them (to copy their files safely)"
for PGD in "$HOME/timetable-pg" "$PREFIX/var/lib/postgresql"; do
  [ -f "$PGD/PG_VERSION" ] || continue
  tag=$(basename "$PGD"); was_running=1
  if ! pg_ctl -D "$PGD" status >/dev/null 2>&1; then
    was_running=0; rm -f "$PGD/postmaster.pid"
    pg_ctl -D "$PGD" -l "$MOVE/pg-$tag.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null 2>&1 || true
    PORT=5499
  else
    PORT=$(sed -n 4p "$PGD/postmaster.pid" 2>/dev/null); PORT=${PORT:-5432}
  fi
  if pg_dumpall -h 127.0.0.1 -p "$PORT" -U postgres > "$MOVE/pg-$tag.sql" 2>/dev/null \
     || pg_dumpall -h 127.0.0.1 -p "$PORT" > "$MOVE/pg-$tag.sql" 2>/dev/null; then
    echo "  OK $tag: $(du -h "$MOVE/pg-$tag.sql" | cut -f1)"
  else
    echo "  ! $tag: no SQL copy - only the database files are moved"; rm -f "$MOVE/pg-$tag.sql"
  fi
  cat "$PGD/PG_VERSION" > "$MOVE/pg-$tag.version"
  pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
  [ $was_running = 0 ] || echo "  ($tag was stopped; start it again later if you need it on this phone)"
done

say "4) Password for the file (you need it on the new phone - do not send it with the file)"
while true; do
  read -r -s -p "  Password (8+ characters): " P1 </dev/tty; echo
  read -r -s -p "  Type it again: " P2 </dev/tty; echo
  [ ${#P1} -ge 8 ] && [ "$P1" = "$P2" ] && break
  echo "  - too short or not the same"
done
export MOVE_PASS="$P1"

OUT="$HOME/storage/downloads/termux-move-$STAMP.tgz.enc"
EX=(--exclude=./storage --exclude=./.cache --exclude=./.npm --exclude=./.bash_history --exclude='*/__pycache__'
    --exclude='*/node_modules' --exclude='./*/logs/*.log' --exclude='./*.log')
if [ "$ALL" != 1 ]; then for d in $SKIP_OLD; do EX+=(--exclude="./$d"); done; fi
say "5) Packing and encrypting the home folder - this can take a few minutes"
cd "$HOME"
tar -czf - "${EX[@]}" . | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:MOVE_PASS -out "$OUT"
unset MOVE_PASS P1 P2
SUM=$(sha256sum "$OUT" | cut -c1-16)
rm -rf "$MOVE"

say "DONE: $(du -h "$OUT" | cut -f1)  Downloads/$(basename "$OUT")  (fingerprint $SUM)"
echo "  Not included: $SKIP_OLD (old folders) - to include them: ALL=1 before the command"
if rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
  read -r -p "  Also upload the encrypted file to Drive (gdrive:IAJ-backups/phone-move)? (y/N): " UP </dev/tty
  if [ "$UP" = y ] || [ "$UP" = Y ]; then
    rclone copy "$OUT" gdrive:IAJ-backups/phone-move --progress && echo "  OK uploaded to Drive" || echo "  ! upload failed - move the file by hand"
  fi
fi
echo
echo "  NEXT: put the file in the Download folder of the NEW phone (cable, Google Drive app, Nearby Share),"
echo "  then on the new phone:"
echo "  curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_in.sh | bash"
echo "  Do not run emergency mode from both phones at the same time."
