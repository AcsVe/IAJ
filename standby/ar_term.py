"""Readable Arabic in Termux: Termux draws Arabic letters one by one, unjoined and left to right. This filter
sits between the phone scripts and the screen (standby/arabic.sh): every line that has Arabic is joined
(arabic-reshaper), put in visual right-to-left order (python-bidi) and aligned to the right edge; other lines
pass through untouched. Without the two libraries it passes everything through as it is.
"""
import os
import re
import sys

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:          # noqa: BLE001 - no libraries: show the text as it is
    arabic_reshaper = None

ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')
ARABIC = re.compile('[؀-ۿ]')
MARKS = {'✓': '\x1b[1;32m', '✗': '\x1b[1;31m', '!': '\x1b[1;33m', '→': '\x1b[2m', '»': '\x1b[1;36m'}
OFF = '\x1b[0m'


def width():
    try:
        cols = os.get_terminal_size(sys.stdout.fileno()).columns
    except OSError:
        cols = 0
    return cols or int(os.environ.get('COLUMNS') or 0)


def shape(line):
    if arabic_reshaper is None or not ARABIC.search(line):
        return line
    end = '\n' if line.endswith('\n') else ''
    body = line[:-1] if end else line
    body = body.split('\r')[-1]
    plain = ANSI.sub('', body)
    lead = re.match(r' *((?:\x1b\[[0-9;]*m)*)', body).group(1)    # colour of the whole line (titles, notes)
    if lead and plain.strip(' ')[:1] in MARKS:                      # a coloured mark, not a coloured line
        lead = ''
    indent = len(plain) - len(plain.lstrip(' '))
    text = plain.strip(' ')
    # addresses that start with a digit (2.iajaward.org) stay in one piece: a left-to-right mark before them
    text = re.sub(r'(?<![\w.])(\d[\w-]*\.[A-Za-z][\w./-]*)', '\u200e\\1', text)
    visual = get_display(arabic_reshaper.reshape(text)).replace('\u200e', '')
    for mark, colour in MARKS.items():                            # keep the colour of the ✓ ! ✗ marks
        if visual.endswith(mark) or visual.endswith(mark + ' '):
            i = visual.rfind(mark)
            visual = visual[:i] + colour + mark + OFF + (lead if lead else '') + visual[i + 1:]
            break
    first = re.search('[A-Za-z\u0600-\u06FF]', text)              # base direction: the first letter
    rtl = bool(first and ARABIC.match(first.group(0)))
    cols = 0 if (os.environ.get('AR_NOPAD') or not rtl) else width()
    pad = max(0, cols - len(ANSI.sub('', visual)) - indent - 1) if cols else 0
    return ' ' * pad + lead + visual + (OFF if lead else '') + ' ' * indent + end


def main():
    out = sys.stdout
    for line in iter(sys.stdin.readline, ''):
        try:
            out.write(shape(line))
        except Exception:          # noqa: BLE001 - never lose a line because of the shaping
            out.write(line)
        out.flush()


if __name__ == '__main__':
    main()
