from .site_cache import get_site_bundle


def ticker_context(request):
    b = get_site_bundle()
    return {
        'global_ticker_items': b['global_ticker_items'],
        'global_ticker_settings': b['global_ticker_settings'],
    }


def site_context(request):
    """بيانات مشتركة لكل الصفحات — من الذاكرة المؤقتة (انظر site_cache.py)"""
    b = get_site_bundle()
    return {k: b[k] for k in ('settings', 'theme', 'content', 'footer', 'section_bgs')}
