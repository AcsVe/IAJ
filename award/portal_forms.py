import os

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.models import User

from .models import Area, Directorate, Field, Governorate, Profile, Submission

INPUT = {'class': 'form-control'}


def location_json():
    """بيانات القوائم المترابطة: المحافظة ← الألوية + المديريات"""
    import json
    data = {'g': {}, 'general': [[d.pk, d.name] for d in Directorate.objects.filter(governorate__isnull=True, is_active=True)]}
    for g in Governorate.objects.all():
        data['g'][str(g.pk)] = {'areas': [], 'dirs': []}
    for a in Area.objects.all():
        data['g'].setdefault(str(a.governorate_id), {'areas': [], 'dirs': []})['areas'].append([a.pk, a.name, a.directorate_id])
    for d in Directorate.objects.filter(governorate__isnull=False, is_active=True):
        data['g'].setdefault(str(d.governorate_id), {'areas': [], 'dirs': []})['dirs'].append([d.pk, d.name])
    return json.dumps(data, ensure_ascii=False)


class LocationMixin:
    """حقول المحافظة / اللواء / المديرية — مترابطة ومتحقّق منها"""
    def _add_location_fields(self, required=True):
        self.fields['governorate'] = forms.ModelChoiceField(Governorate.objects.all(), label='المحافظة', required=required,
                                                            empty_label='— اختر المحافظة —', widget=forms.Select(attrs={'class': 'form-select', 'data-loc': 'gov'}))
        self.fields['area'] = forms.ModelChoiceField(Area.objects.all(), label='اللواء / المدينة', required=required,
                                                     empty_label='— اختر اللواء —', widget=forms.Select(attrs={'class': 'form-select', 'data-loc': 'area'}))
        self.fields['directorate'] = forms.ModelChoiceField(Directorate.objects.filter(is_active=True), label='مديرية التربية والتعليم',
                                                            required=required, empty_label='— اختر المديرية —',
                                                            widget=forms.Select(attrs={'class': 'form-select', 'data-loc': 'dir'}))

    def _clean_location(self, data):
        g, a, d = data.get('governorate'), data.get('area'), data.get('directorate')
        if g and a and a.governorate_id != g.pk:
            self.add_error('area', 'هذا اللواء لا يتبع المحافظة المختارة.')
        if g and d and d.governorate_id not in (None, g.pk):
            self.add_error('directorate', 'هذه المديرية لا تتبع المحافظة المختارة.')
SELECT = {'class': 'form-select'}


def _w(widget_cls, ph='', **extra):
    attrs = dict(INPUT, **extra)
    if ph:
        attrs['placeholder'] = ph
    return widget_cls(attrs=attrs)


class SchoolSignupForm(LocationMixin, forms.Form):
    school_name = forms.CharField(label='اسم المدرسة', max_length=255, widget=_w(forms.TextInput, 'اسم المدرسة كما سيظهر في الشهادات'))
    contact_person = forms.CharField(label='ضابط الارتباط', max_length=255, widget=_w(forms.TextInput, 'الاسم الكامل'))
    email = forms.EmailField(label='البريد الإلكتروني', widget=_w(forms.EmailInput, 'name@example.com', autocomplete='email', dir='ltr'))
    phone = forms.CharField(label='رقم الهاتف', max_length=30, widget=_w(forms.TextInput, '07xxxxxxxx', dir='ltr', inputmode='tel'))
    password1 = forms.CharField(label='كلمة المرور', widget=_w(forms.PasswordInput, '8 أحرف على الأقل', autocomplete='new-password'))
    password2 = forms.CharField(label='تأكيد كلمة المرور', widget=_w(forms.PasswordInput, 'أعد كتابتها', autocomplete='new-password'))
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))  # فخ للروبوتات

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._add_location_fields()

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('هذا البريد مسجّل مسبقاً — استخدم «تسجيل الدخول» أو «نسيت كلمة المرور».')
        return email

    def clean(self):
        data = super().clean()
        self._clean_location(data)
        if data.get('website'):
            raise forms.ValidationError('تعذّر التسجيل.')
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'كلمتا المرور غير متطابقتين.')
        elif p1:
            tmp = User(username=data.get('email', ''), email=data.get('email', ''), first_name=data.get('contact_person', ''))
            try:
                password_validation.validate_password(p1, tmp)
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(username=d['email'], email=d['email'], password=d['password1'],
                                        first_name=d['contact_person'][:150], is_active=False)
        Profile.objects.create(user=user, role='school', school_name=d['school_name'],
                               contact_person=d['contact_person'], phone=d['phone'],
                               governorate=d.get('governorate'), area=d.get('area'), directorate=d.get('directorate'),
                               city=d['area'].name if d.get('area') else '')
        return user


class ProfileForm(LocationMixin, forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['school_name', 'contact_person', 'phone', 'governorate', 'area', 'directorate', 'email_notifications']
        widgets = {
            'school_name': _w(forms.TextInput), 'contact_person': _w(forms.TextInput),
            'phone': _w(forms.TextInput, dir='ltr'),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        is_school = self.instance.role != 'judge'
        self._add_location_fields(required=is_school)
        for f in ('governorate', 'area', 'directorate'):
            self.fields[f].initial = getattr(self.instance, f + '_id')
        if self.instance.role == 'judge':
            self.fields['school_name'].label = 'الجهة'
            self.fields['contact_person'].label = 'الاسم'

    def clean(self):
        data = super().clean()
        self._clean_location(data)
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if obj.area_id:
            obj.city = obj.area.name
        if commit:
            obj.save()
        return obj


def _check_file(f, exts, label):
    if not f or not hasattr(f, 'size'):
        return f
    ext = os.path.splitext(f.name)[1].lower()
    if exts and ext not in exts:
        raise forms.ValidationError(f'{label}: الصيغ المسموحة {" ".join(exts)}')
    limit = settings.SUBMISSION_MAX_MB
    if f.size > limit * 1024 * 1024:
        raise forms.ValidationError(f'{label}: الحجم الأقصى {limit} ميغابايت.')
    return f


DOC_EXTS = ['.pdf']
ATTACH_EXTS = ['.pdf', '.zip', '.rar', '.7z', '.pptx', '.ppt', '.docx', '.doc', '.xlsx',
               '.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov']


class PortalSubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['field', 'track', 'project_title', 'abstract', 'team_members', 'supervisor',
                  'contact_person', 'phone', 'document', 'attachment']
        widgets = {
            'field': forms.Select(attrs=SELECT), 'track': forms.Select(attrs=SELECT),
            'project_title': _w(forms.TextInput, 'عنوان المشروع'),
            'abstract': _w(forms.Textarea, 'فكرة المشروع، أهدافه، وأهم نتائجه', rows=5),
            'team_members': _w(forms.Textarea, 'اسم الطالب — الصف (كل اسم في سطر)', rows=4),
            'supervisor': _w(forms.TextInput, 'اسم المعلم المشرف'),
            'contact_person': _w(forms.TextInput), 'phone': _w(forms.TextInput, dir='ltr'),
            'document': forms.ClearableFileInput(attrs=dict(INPUT, accept='.pdf')),
            'attachment': forms.ClearableFileInput(attrs=INPUT),
        }

    def __init__(self, *a, cycle=None, **kw):
        super().__init__(*a, **kw)
        tracks = cycle.available_tracks() if cycle else self.fields['track'].queryset.none()
        self.fields['track'].queryset = tracks
        self.fields['field'].queryset = Field.objects.filter(pk__in=tracks.values('field_id'))
        self.fields['field'].required = True
        self.fields['track'].required = True
        self.fields['field'].empty_label = '— اختر المجال —'
        self.fields['track'].empty_label = '— اختر المسار —'
        self.fields['document'].help_text = f'PDF — حتى {settings.SUBMISSION_MAX_MB} ميغابايت. مطلوب عند الإرسال.'
        self.fields['attachment'].help_text = f'اختياري — PDF، عرض تقديمي، صور، فيديو قصير أو ملف مضغوط (حتى {settings.SUBMISSION_MAX_MB} ميغابايت).'

    def clean_document(self):
        return _check_file(self.cleaned_data.get('document'), DOC_EXTS, 'ملف البحث')

    def clean_attachment(self):
        return _check_file(self.cleaned_data.get('attachment'), ATTACH_EXTS, 'المرفق')

    def clean(self):
        data = super().clean()
        f, t = data.get('field'), data.get('track')
        if f and t and t.field_id != f.pk:
            self.add_error('track', 'هذا المسار لا يتبع المجال المختار.')
        return data


from django.contrib.auth.forms import PasswordResetForm as _PRF


class SafePasswordResetForm(_PRF):
    """استعادة كلمة المرور بقالب الجائزة — والإرسال في الخلفية حتى لا تتعطل الصفحة لو فشل البريد"""
    email = forms.EmailField(label='البريد الإلكتروني', widget=_w(forms.EmailInput, 'name@example.com', dir='ltr', autocomplete='email'))

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        from .notify import send_email
        url = f"{context['protocol']}://{context['domain']}/accounts/reset/{context['uid']}/{context['token']}/"
        user = context.get('user')
        send_email(to_email, 'استعادة كلمة المرور — جائزة انتصار عباس جردانة',
                   f"مرحباً {getattr(user, 'first_name', '') or ''}،\nوصلنا طلب لتعيين كلمة مرور جديدة لحسابكم. "
                   "اضغطوا الزر لاختيار كلمة مرور جديدة.\nإذا لم تطلبوا ذلك تجاهلوا هذه الرسالة.",
                   url, 'تعيين كلمة مرور جديدة')
