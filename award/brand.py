"""
لون القائمة (نفس لون الهيدر في الموقع = اللون الأساسي) — يُستخدم في المراسلات وصفحات الحساب
بتدرّج زجاجي. يتغيّر تلقائياً عند تغيير اللون من لوحة التحكم.
"""
from .models import shade


def _rgb(h):
    h = (h or '').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        return ','.join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))
    except ValueError:
        return '10,22,50'


def brand_colors():
    from .site_cache import get_site_bundle
    b = get_site_bundle()
    ticker, theme = b.get('global_ticker_settings'), b.get('theme')
    def _hex(v, default):
        v = (v or '').strip() or default
        return v if v.startswith('#') else '#' + v
    menu = _hex(getattr(theme, 'primary_color', ''), '#0a1632')          # لون الهيدر (القائمة) على الكمبيوتر
    nav = _hex(getattr(ticker, 'bg_color', ''), menu)                    # لون القائمة على الموبايل
    gold = (getattr(theme, 'gold_color', '') or '#c5a059').strip()
    return {
        'menu': menu,
        'menu_rgb': _rgb(menu),
        'menu_light': shade(menu, 0.14),
        'menu_dark': shade(menu, -0.22),
        'menu_deep': shade(menu, -0.45),
        'nav': nav, 'nav_light': shade(nav, 0.14), 'nav_dark': shade(nav, -0.22),
        # درجات داكنة من لون الهيدر — بدل الكحلي القديم في البطاقات والنوافذ والزجاجيات
        'deep1_rgb': _rgb(shade(menu, -0.30)),
        'deep2_rgb': _rgb(shade(menu, -0.50)),
        'deep3_rgb': _rgb(shade(menu, -0.68)),
        'gold': gold,
        'gold_rgb': _rgb(gold),
    }
