#!/data/data/com.termux/files/usr/bin/bash
# ================================================================
#  Move Termux to a new phone - step 2, on the NEW phone
#  (English messages: Termux does not join or right-to-left Arabic)
#
#  Before: install Termux, Termux:API, Termux:Widget and Termux:Boot from the SAME source
#  (F-Droid or GitHub), open Termux:Boot once, and copy termux-move-*.tgz.enc to the phone.
#
#   curl -fsSL https://raw.githubusercontent.com/AcsVe/IAJ/main/standby/phone_move_in.sh | bash
#   (or with the file path:  ... | bash -s /sdcard/Download/termux-move-....tgz.enc)
#  If the file is only in Google Drive: the script can download it (sets up rclone for you).
# ================================================================
set -e
say() { printf '\n\033[1;36m> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mX %s\033[0m\n' "$*"; exit 1; }
MOVE="$HOME/.move"

say "1) Preparing Termux"
yes | pkg update -y >/dev/null 2>&1 || pkg update -y
pkg install -y openssl-tool tar termux-services >/dev/null
if [ ! -d "$HOME/storage/shared" ]; then
  echo "  Allow Termux to access files on the phone (a window will appear)..."
  termux-setup-storage; sleep 6
fi

find_file() {
  for dir in "$HOME/storage/downloads" /sdcard/Download /storage/emulated/0/Download /sdcard; do
    [ -d "$dir" ] || continue
    find "$dir" -maxdepth 3 -type f -iname 'termux-move*' 2>/dev/null
  done | xargs -r ls -t 2>/dev/null | head -1
}
F="$1"
[ -n "$F" ] || F=$(find_file)
if [ ! -f "$F" ]; then
  echo "  The file termux-move-*.tgz.enc is not on this phone (looked in Download and the phone storage)."
  read -r -p "  Download it from Google Drive (IAJ-backups/phone-move) now? (y/N): " G </dev/tty
  if [ "$G" = y ] || [ "$G" = Y ]; then
    pkg install -y rclone >/dev/null
    if ! rclone listremotes 2>/dev/null | grep -q '^gdrive:'; then
      echo "  Setting up Google Drive: answer   n  >  name: gdrive  >  storage: drive  >  Enter for the rest,"
      echo "  'Use web browser to authenticate' = y, sign in with the school Google account, then q to quit."
      rclone config </dev/tty
    fi
    mkdir -p "$HOME/storage/downloads"
    rclone copy gdrive:IAJ-backups/phone-move "$HOME/storage/downloads" --include 'termux-move-*' --max-age 30d --progress </dev/tty || true
    F=$(find_file)
  fi
fi
[ -f "$F" ] || die "File not found. Copy termux-move-*.tgz.enc into the Download folder of this phone, then run again (or give its path after: bash -s)"
echo "  File: $F ($(du -h "$F" | cut -f1), fingerprint $(sha256sum "$F" | cut -c1-16))"

if [ -n "$(ls -A "$HOME" 2>/dev/null | grep -v '^storage$\|^\.termux$\|^\.bash_history$\|^\.config$\|^\.cache$')" ]; then
  echo "  ! The home folder is not empty; files with the same names will be replaced."
  read -r -p "  Continue? type YES: " OK </dev/tty
  [ "$OK" = YES ] || die "Cancelled"
fi

say "2) Decrypting and restoring"
ok=0
for i in 1 2 3; do
  read -r -s -p "  Password of the file: " MOVE_PASS </dev/tty; echo; export MOVE_PASS
  if openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:MOVE_PASS -in "$F" | tar -xzf - -C "$HOME" 2>"$HOME/.move-err"; then
    ok=1; break
  fi
  echo "  - wrong password or incomplete file"
done
unset MOVE_PASS
[ "$ok" = 1 ] || die "Could not restore: $(tail -2 "$HOME/.move-err")"
rm -f "$HOME/.move-err"
[ -d "$MOVE" ] || die "The file has no package list (.move) - was it made by phone_move_out.sh?"
[ "$(cat "$MOVE/arch.txt")" = "$(uname -m)" ] || echo "  ! different processor ($(cat "$MOVE/arch.txt") -> $(uname -m)); libraries are reinstalled anyway"

say "3) Packages (pkg) - several minutes"
grep -qx tur-repo "$MOVE/pkgs.txt" && { pkg install -y tur-repo >/dev/null 2>&1; pkg update -y >/dev/null 2>&1; } || true
grep -qx sshd "$MOVE/services.txt" && echo openssh >> "$MOVE/pkgs.txt" || true
if ! pkg install -y $(cat "$MOVE/pkgs.txt") >/dev/null 2>&1; then
  for p in $(cat "$MOVE/pkgs.txt"); do pkg install -y "$p" >/dev/null 2>&1 || echo "  ! not installed: $p"; done
fi

say "4) Python libraries (pip)"
# libraries that pkg builds for Termux are not reinstalled with pip
grep -viE '^(pip|numpy|pandas|pillow|cryptography|cffi|pycparser|lxml)==' "$MOVE/pip.txt" > "$MOVE/pip-req.txt" || true
if ! pip install -q -r "$MOVE/pip-req.txt" 2>/dev/null; then
  while read -r line; do
    [ -n "$line" ] || continue
    pip install -q "$line" 2>/dev/null || pip install -q "${line%%==*}" 2>/dev/null || echo "  ! not installed: $line"
  done < "$MOVE/pip-req.txt"
fi

if [ -s "$MOVE/npm.txt" ]; then
  say "5) npm tools"
  npm install -g $(cat "$MOVE/npm.txt") >/dev/null 2>&1 || echo "  ! some failed: $(tr '\n' ' ' < "$MOVE/npm.txt")"
fi

say "6) PostgreSQL databases"
for PGD in "$HOME/timetable-pg" "$PREFIX/var/lib/postgresql"; do
  tag=$(basename "$PGD"); dump="$MOVE/pg-$tag.sql"
  [ -f "$dump" ] || [ -f "$PGD/PG_VERSION" ] || continue
  rm -f "$PGD/postmaster.pid"
  if [ -f "$PGD/PG_VERSION" ] && pg_ctl -D "$PGD" -l "$HOME/pg-move.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null 2>&1; then
    pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
    echo "  OK $tag: database files work as they are"
    continue
  fi
  [ -f "$dump" ] || { echo "  ! $tag: does not start and has no SQL copy"; continue; }
  [ -d "$PGD" ] && mv "$PGD" "$PGD.old-$(date +%s)"
  initdb -D "$PGD" -U postgres --auth=trust -E UTF8 --locale=C >/dev/null
  pg_ctl -D "$PGD" -l "$HOME/pg-move.log" -o "-p 5499 -c listen_addresses=127.0.0.1 -k ${TMPDIR:-$HOME}" -w start >/dev/null
  psql -q -h 127.0.0.1 -p 5499 -U postgres -d postgres -f "$dump" >/dev/null 2>"$HOME/pg-move-restore.log" || true
  pg_ctl -D "$PGD" -m fast stop >/dev/null 2>&1 || true
  echo "  OK $tag: rebuilt from the SQL copy (old files kept in $PGD.old-*)"
done

say "7) Services and permissions"
for s in $(cat "$MOVE/services.txt" 2>/dev/null); do
  sv-enable "$s" >/dev/null 2>&1 && echo "  OK $s" || echo "  ! $s - after reopening Termux run: sv-enable $s"
done
chmod 600 "$HOME"/.*_token "$HOME"/.*_standby 2>/dev/null || true
chmod 700 "$HOME/.ssh" 2>/dev/null && chmod 600 "$HOME"/.ssh/* 2>/dev/null || true
chmod +x "$HOME"/.shortcuts/* "$HOME"/.termux/boot/* 2>/dev/null || true
for f in "$HOME"/*/standby/*.sh; do sed -i 's/\r$//' "$f" 2>/dev/null || true; done
rm -rf "$MOVE"

say "DONE - the move is complete"
cat <<'EOF'
  Left to do on the new phone:
  1. Close Termux and open it again (so the services start), then refresh the Termux:Widget.
  2. Android settings: turn OFF battery optimisation for Termux and Termux:Boot.
  3. Try the buttons: 'IAJ 3' (where the site runs), then 'IAJ 8' (test on the phone only).
  4. After checking, delete termux-move-*.tgz.enc from Download and from Drive.
  Do not run emergency mode from both phones at the same time.
EOF
