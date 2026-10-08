from django import template
from django.utils import timezone

register = template.Library()
AR_MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']


@register.filter
def ar_date(value):
    """29 أكتوبر 2026"""
    if not value:
        return ''
    try:
        if hasattr(value, 'tzinfo') and value.tzinfo is not None:
            value = timezone.localtime(value)
        return f"{value.day} {AR_MONTHS[value.month - 1]} {value.year}"
    except Exception:
        return value


@register.filter
def iaj_can_preview(opts):
    """هل يمكن معاينة هذا الجدول قبل الحفظ؟ (محتوى الموقع والتصميم)"""
    from award.admin_tools import can_preview
    return can_preview(opts)
