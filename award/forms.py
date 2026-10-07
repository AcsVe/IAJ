from django import forms
from .models import Submission

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['school_name', 'contact_person', 'email', 'phone', 'field', 'track', 'project_title', 'document']
        widgets = {
            'school_name': forms.TextInput(attrs={'class': 'form-control bg-white text-dark', 'placeholder': 'اسم المدرسة'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control bg-white text-dark', 'placeholder': 'ضابط الارتباط'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-white text-dark', 'placeholder': 'البريد الإلكتروني'}),
            'phone': forms.TextInput(attrs={'class': 'form-control bg-white text-dark', 'placeholder': 'رقم الهاتف'}),
            'field': forms.Select(attrs={'class': 'form-select bg-white text-dark'}),
            'track': forms.Select(attrs={'class': 'form-select bg-white text-dark'}),
            'project_title': forms.TextInput(attrs={'class': 'form-control bg-white text-dark', 'placeholder': 'عنوان المشروع'}),
            'document': forms.FileInput(attrs={'class': 'form-control bg-white text-dark'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # المسارات المعطّلة لا تظهر في النموذج ولا تُقبل
        from .models import Track
        self.fields['track'].queryset = Track.objects.filter(is_active=True)
