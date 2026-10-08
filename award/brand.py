"""
لون القائمة (نفس لون شريط الأخبار/القائمة في الموقع) — يُستخدم في المراسلات وصفحات الحساب
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
    menu = (getattr(ticker, 'bg_color', '') or getattr(theme, 'primary_color', '') or '#0a1632').strip()
    if not menu.startswith('#'):
        menu = '#' + menu
    gold = (getattr(theme, 'gold_color', '') or '#c5a059').strip()
    return {
        'menu': menu,
        'menu_rgb': _rgb(menu),
        'menu_light': shade(menu, 0.22),
        'menu_dark': shade(menu, -0.38),
        'menu_deep': shade(menu, -0.6),
        'gold': gold,
        'gold_rgb': _rgb(gold),
    }
