from django import forms
from .models import QuestionUpload, Content, Subject, Standard

class QuestionUploadForm(forms.ModelForm):
    """Form for uploading questions via Word file"""
    class Meta:
        model = QuestionUpload
        fields = ['file', 'subject', 'standard']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.docx',
                'required': True
            }),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'standard': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'file': 'Word Document (.docx)',
            'subject': 'Subject',
            'standard': 'Standard/Class',
        }

class ContentUploadForm(forms.ModelForm):
    """Form for uploading PDF content"""
    class Meta:
        model = Content
        fields = ['title', 'description', 'file', 'subject', 'standard', 'is_public']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter content title',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter description (optional)'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'application/pdf,.pdf',
                'required': True
            }),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'standard': forms.Select(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title': 'Content Title',
            'description': 'Description',
            'file': 'PDF File',
            'subject': 'Subject (Optional)',
            'standard': 'Standard/Class (Optional)',
            'is_public': 'Make this content public',
        }
        help_texts = {
            'is_public': 'If checked, content will be visible to all institutions',
        }

class StudentInfoForm(forms.Form):
    """Form for student profile completion"""
    student_name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your full name'
        }),
        label='Full Name'
    )
    roll_number = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your roll number'
        }),
        label='Roll Number'
    )
