# Sourced by the phone scripts (panel.sh, doctor.sh, phone.sh of every system) right after LANG_UI is set:
# when the messages are in Arabic and go to the Termux screen, they pass through ar_term.py, which joins the
# letters and writes them right to left. Child scripts inherit the filtered output (they are not filtered twice).
if [ "${LANG_UI:-ar}" = "ar" ] && [ -t 1 ] && [ -z "$IAJ_AR_FILTER" ] && [ -f "$HOME/iaj/standby/ar_term.py" ] \
   && python -c "import arabic_reshaper, bidi.algorithm" 2>/dev/null; then
  export IAJ_AR_FILTER=1 COLUMNS="${COLUMNS:-$(tput cols 2>/dev/null || echo 0)}"
  exec > >(python -u "$HOME/iaj/standby/ar_term.py")
  IAJ_AR_PID=$!
  trap 'exec >&- 2>/dev/null; wait "$IAJ_AR_PID" 2>/dev/null' EXIT
fi

# a prompt for read -p (written to the keyboard side, so it is shaped here, without right alignment)
ar_prompt() {
  if [ -n "$IAJ_AR_FILTER" ]; then printf '%s\n' "$1" | AR_NOPAD=1 python "$HOME/iaj/standby/ar_term.py" | tr -d '\n'
  else printf '%s' "$1"; fi
}
