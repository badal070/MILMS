from django import forms
from .models import QuestionUpload, Content, Subject, Standard, DescriptiveQuestionUpload, DescriptiveQuestion

class QuestionUploadForm(forms.ModelForm):
    """Enhanced form for uploading questions via Word or PDF file"""
    class Meta:
        model = QuestionUpload
        fields = ['file', 'subject', 'standard']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.docx,.pdf',  # Accept both formats
                'required': True
            }),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'standard': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'file': 'Question File (.docx or .pdf)',
            'subject': 'Subject',
            'standard': 'Standard/Class',
        }
        help_texts = {
            'file': 'Upload a Word (.docx) or PDF (.pdf) file containing questions in standard format',
        }
    
    def clean_file(self):
        """Validate file type and size"""
        file = self.cleaned_data.get('file')
        
        if file:
            # Check file extension
            file_ext = file.name.split('.')[-1].lower()
            if file_ext not in ['docx', 'pdf']:
                raise forms.ValidationError(
                    'Invalid file type. Only .docx and .pdf files are allowed.'
                )
            
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    'File size too large. Maximum size is 10MB.'
                )
        
        return file


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
            'file': 'Upload a PDF file (Max 10MB)',
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


class DescriptiveQuestionUploadForm(forms.ModelForm):
    """Form for uploading descriptive questions via Word file"""
    class Meta:
        model = DescriptiveQuestionUpload
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
        help_texts = {
            'file': 'Upload a .docx file with descriptive questions',
        }


class DescriptiveQuestionForm(forms.ModelForm):
    """Form for creating/editing descriptive questions"""
    class Meta:
        model = DescriptiveQuestion
        fields = [
            'subject', 'standard', 'question_text', 'reference_answer',
            'marking_guidelines', 'max_marks', 'word_limit',
            'enable_ai_evaluation', 'ai_evaluation_weightage', 'is_active'
        ]
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'standard': forms.Select(attrs={'class': 'form-select'}),
            'question_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter the descriptive question...'
            }),
            'reference_answer': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Enter reference/model answer for AI evaluation...'
            }),
            'marking_guidelines': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Key points to look for when marking...'
            }),
            'max_marks': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 100
            }),
            'word_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 50
            }),
            'enable_ai_evaluation': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'ai_evaluation_weightage': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 0.01,
                'min': 0,
                'max': 1
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }