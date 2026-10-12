"""سجل العمليات الحساسة: من فعل ماذا ومتى (حذف، نشر، اعتماد، تصدير، تنظيف، محاكاة، دخول الإدارة)."""
import logging

log = logging.getLogger('iaj')


def _ip(request):
    if not request:
        return ''
    return (request.META.get('HTTP_CF_CONNECTING_IP') or request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0]
            or request.META.get('REMOTE_ADDR') or '')[:45]


def audit(request_or_user, action, target='', detail=''):
    """يسجّل عملية — لا يوقف أي شيء لو فشل"""
    from .models import AuditLog
    request = request_or_user if hasattr(request_or_user, 'META') else None
    user = getattr(request, 'user', None) if request else request_or_user
    if user is not None and not getattr(user, 'is_authenticated', False):
        user = None
    try:
        AuditLog.objects.create(user=user, action=str(action)[:60], target=str(target)[:255],
                                detail=str(detail)[:5000], ip=_ip(request))
    except Exception as e:   # noqa: BLE001
        log.warning('audit failed: %s', e)
