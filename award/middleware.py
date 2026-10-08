from django.utils import translation


class AdminArabicMiddleware:
    """لوحة Django بالعربية ومن اليمين لليسار (RTL).
    يُفعَّل للوحة التحكم فقط؛ صفحات الموقع تبقى بإعداداتها حتى لا تتغيّر صيغة الأرقام في الـ CSS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            with translation.override('ar'):
                request.LANGUAGE_CODE = 'ar'
                response = self.get_response(request)
                if hasattr(response, 'render') and not getattr(response, 'is_rendered', True):
                    response.render()
                response.setdefault('Content-Language', 'ar')
                return response
        return self.get_response(request)
