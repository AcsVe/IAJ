"""الدخول بالبريد الإلكتروني أو اسم المستخدم (لحسابات الإدارة القديمة)"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        login = (username or kwargs.get('email') or '').strip()
        if not login or not password:
            return None
        user = User.objects.filter(username__iexact=login).first()
        if user is None and '@' in login:
            user = User.objects.filter(email__iexact=login).order_by('id').first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        User().set_password(password)   # توحيد زمن الاستجابة
        return None
