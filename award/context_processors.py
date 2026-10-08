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


def portal_context(request):
    """الجرس + حالة الدخول + موعد العداد (من الدورة الحالية إن وُجدت)"""
    from django.core.cache import cache
    from django.utils import timezone
    data = {}
    cyc = cache.get('iaj_current_cycle', 'none')
    if cyc == 'none':
        from .models import AwardCycle
        c = AwardCycle.current()
        cyc = {'name': c.name, 'opens_at': c.opens_at, 'closes_at': c.closes_at} if c else None
        cache.set('iaj_current_cycle', cyc, 60)
    now = timezone.now()
    if cyc and cyc['opens_at'] <= now <= cyc['closes_at']:
        data['reg_deadline'] = cyc['closes_at']
        data['reg_open'] = True
    elif cyc:
        data['reg_deadline'] = None
        data['reg_open'] = False
        data['reg_opens_at'] = cyc['opens_at'] if now < cyc['opens_at'] else None
    else:
        b = get_site_bundle()
        st = b.get('settings')
        data['reg_deadline'] = st.registration_deadline if st else None
        data['reg_open'] = True
    try:
        from .brand import brand_colors
        data['brand'] = brand_colors()
    except Exception:
        pass
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        prof = getattr(user, 'profile', None)
        data['portal_role'] = prof.role if prof else ('staff' if user.is_staff else 'school')
        data['unread_notes'] = user.notifications.filter(is_read=False).count()
    return data
