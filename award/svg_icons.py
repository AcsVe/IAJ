"""أيقونات SVG مدمجة بدل خط Font Awesome الخارجي.

كل <i class="fas fa-xxx"></i> في أي صفحة يُملأ تلقائياً بـ <svg> مرسوم (انظر SvgIconsMiddleware)،
فلا يُحمَّل أي خط أيقونات من الإنترنت. يعمل أيضاً مع الأيقونات المكتوبة في لوحة التحكم (مثل fa-star).
بيانات الأيقونات: award/icons/fa.json (Font Awesome Free 6.5.1 — CC BY 4.0).
"""
import json
import os
import re
from functools import lru_cache

_DATA_PATH = os.path.join(os.path.dirname(__file__), 'icons', 'fa.json')

# فئات تعديل (ليست أسماء أيقونات)
MODIFIERS = {
    'fa-fw', 'fa-spin', 'fa-pulse', 'fa-spin-pulse', 'fa-spin-reverse', 'fa-beat', 'fa-fade', 'fa-beat-fade',
    'fa-bounce', 'fa-flip', 'fa-shake', 'fa-border', 'fa-pull-left', 'fa-pull-right', 'fa-inverse', 'fa-li', 'fa-ul',
    'fa-xs', 'fa-sm', 'fa-lg', 'fa-xl', 'fa-2xs', 'fa-2xl', 'fa-1x', 'fa-2x', 'fa-3x', 'fa-4x', 'fa-5x', 'fa-6x',
    'fa-7x', 'fa-8x', 'fa-9x', 'fa-10x', 'fa-rotate-90', 'fa-rotate-180', 'fa-rotate-270', 'fa-rotate-by',
    'fa-flip-horizontal', 'fa-flip-vertical', 'fa-flip-both', 'fa-stack', 'fa-stack-1x', 'fa-stack-2x',
    'fa-solid', 'fa-regular', 'fa-brands', 'fa-light', 'fa-thin', 'fa-duotone', 'fa-sharp',
}
_STYLE = {'fab': 'b', 'fa-brands': 'b', 'far': 'r', 'fa-regular': 'r'}


@lru_cache(maxsize=1)
def _data():
    with open(_DATA_PATH, encoding='utf-8') as fh:
        return json.load(fh)


def _lookup(name, style):
    d = _data()
    name = d['alias'].get(name, name)
    for st in (style, 's', 'r', 'b'):
        if name in d[st]:
            return d[st][name]
    return None


@lru_cache(maxsize=4096)
def svg_for(classes):
    """من فئات مثل 'fas fa-star me-2' ← نص <svg> أو '' إن لم توجد الأيقونة"""
    parts = classes.split()
    style = 's'
    for p in parts:
        if p in _STYLE:
            style = _STYLE[p]
    name = next((p[3:] for p in parts if p.startswith('fa-') and p not in MODIFIERS), None)
    if not name:
        return ''
    icon = _lookup(name, style)
    if not icon:
        return ''
    w, h, d = icon
    paths = ''.join(f'<path d="{x}"/>' for x in (d if isinstance(d, list) else [d]))
    return (f'<svg class="ic" viewBox="0 0 {w} {h}" width="{w / h:.4g}em" height="1em" fill="currentColor" '
            f'aria-hidden="true" focusable="false">{paths}</svg>')


# <i ... class="... fa-xxx ..." ...></i>  (فارغ) ← نضع الـ SVG داخله ونُبقي العنصر وفئاته كما هي
_I_RE = re.compile(r'(<i\b[^>]*?\bclass\s*=\s*(["\'])([^"\']*\bfa-[^"\']*)\2[^>]*>)\s*(</i>)', re.I)


def fill_icons(html):
    def rep(m):
        svg = svg_for(' '.join(m.group(3).split()))
        return m.group(1) + svg + m.group(4) if svg else m.group(0)
    return _I_RE.sub(rep, html)


def js_map(names):
    """خريطة صغيرة للأيقونات التي تُنشأ بالجافاسكربت بعد تحميل الصفحة"""
    out = {}
    for n in names:
        icon = _lookup(n, 's')
        if icon:
            out[n] = icon
    return out
