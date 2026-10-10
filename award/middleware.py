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


class SvgIconsMiddleware:
    """يملأ كل أيقونة <i class="fa-..."></i> في صفحات HTML بأيقونة SVG مدمجة (بدل خط Font Awesome الخارجي)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(response, 'streaming', False) or response.status_code in (204, 304):
            return response
        if 'text/html' not in response.get('Content-Type', ''):
            return response
        if hasattr(response, 'render') and not getattr(response, 'is_rendered', True):
            response.render()
        try:
            charset = response.charset or 'utf-8'
            html = response.content.decode(charset)
        except (UnicodeDecodeError, AttributeError):
            return response
        if 'fa-' not in html:
            return response
        from .svg_icons import fill_icons
        response.content = fill_icons(html).encode(charset)
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
