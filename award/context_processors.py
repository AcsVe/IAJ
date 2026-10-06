from .models import (
    TickerItem, TickerSetting, SiteSetting, ThemeSetting,
    HomeContent, FooterContent, SectionBackground,
)


def _first(model):
    try:
        return model.objects.first()
    except Exception:
        return None


def ticker_context(request):
    try:
        ticker_items = list(TickerItem.objects.filter(is_active=True))
    except Exception:
        ticker_items = []
    return {
        'global_ticker_items': ticker_items,
        'global_ticker_settings': _first(TickerSetting),
    }


def site_context(request):
    """
    بيانات مشتركة لكل الصفحات (الشعار، الألوان، الفوتر، زر التسجيل...)
    بدونها الصفحات الداخلية كانت تظهر بدون شعار وبفوتر فاضي.
    أي view بيمرّر نفس الأسماء بيغطي على هالقيم.
    """
    try:
        section_bgs = {sb.section_id: sb for sb in SectionBackground.objects.all()}
    except Exception:
        section_bgs = {}
    return {
        'settings': _first(SiteSetting),
        'theme': _first(ThemeSetting),
        'content': _first(HomeContent),
        'footer': _first(FooterContent),
        'section_bgs': section_bgs,
    }
