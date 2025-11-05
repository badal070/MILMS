from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.utils import timezone
from django.db.models import Q

class Institution(models.Model):
    """Educational institution/organization"""
    name = models.CharField(max_length=300, unique=True, db_index=True)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    address = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Institution'
        verbose_name_plural = 'Institutions'
        indexes = [
            models.Index(fields=['name', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

class UserProfile(models.Model):
    """Extended user profile with role and institution"""
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('principal', 'Principal'),
        ('superadmin', 'Super Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student', db_index=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='users', null=True, blank=True, db_index=True)
    
    # Student specific fields
    student_name = models.CharField(max_length=200, blank=True, db_index=True)
    roll_number = models.CharField(max_length=50, blank=True, db_index=True)
    
    # Teacher permissions
    can_create_quiz = models.BooleanField(default=False)
    can_upload_content = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['institution', 'role', 'user__username']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['role', 'institution']),
            models.Index(fields=['student_name']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    @property
    def display_name(self):
        """Return appropriate display name based on role"""
        if self.role == 'student' and self.student_name:
            return self.student_name
        return self.user.get_full_name() or self.user.username

class ActivityLog(models.Model):
    """System-wide activity logging"""
    ACTION_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('quiz_attempt', 'Quiz Attempt'),
        ('quiz_create', 'Quiz Created'),
        ('content_upload', 'Content Uploaded'),
        ('content_view', 'Content Viewed'),
        ('user_create', 'User Created'),
        ('user_update', 'User Updated'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        indexes = [
            models.Index(fields=['-timestamp', 'action']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_action_display()} - {self.timestamp}"

class Subject(models.Model):
    """Academic subjects"""
    name = models.CharField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Standard(models.Model):
    """Academic standards/classes"""
    name = models.CharField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_miscellaneous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Question(models.Model):
    """Quiz questions with multiple choice answers"""
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='questions')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='questions', null=True, blank=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_questions')
    
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subject', 'standard', 'institution']),
        ]

    def __str__(self):
        return f"{self.question_text[:50]}..."

class MarkingScheme(models.Model):
    """Quiz marking/grading scheme"""
    name = models.CharField(max_length=200, unique=True)
    correct_marks = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(0)])
    wrong_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (+{self.correct_marks}, -{self.wrong_marks})"

class Quiz(models.Model):
    """Quiz with questions and settings"""
    title = models.CharField(max_length=300, db_index=True)
    description = models.TextField(blank=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='quizzes')
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE, related_name='quizzes')
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True, db_index=True)
    marking_scheme = models.ForeignKey(MarkingScheme, on_delete=models.PROTECT, related_name='quizzes')
    questions = models.ManyToManyField(Question, related_name='quizzes')
    duration_minutes = models.IntegerField(default=30, validators=[MinValueValidator(1)])
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_quizzes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Quizzes"
        indexes = [
            models.Index(fields=['institution', 'is_active']),
            models.Index(fields=['subject', 'standard']),
        ]

    def __str__(self):
        return self.title

    @property
    def total_questions(self):
        return self.questions.count()

class QuizAttempt(models.Model):
    """Student's quiz attempt record"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total_questions = models.IntegerField(default=0)
    correct_answers = models.IntegerField(default=0)
    wrong_answers = models.IntegerField(default=0)
    unanswered = models.IntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['user', '-started_at']),
            models.Index(fields=['quiz', '-started_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title} - {self.score}"

    @property
    def percentage(self):
        if self.total_questions > 0:
            return round((self.correct_answers / self.total_questions) * 100, 2)
        return 0

class Answer(models.Model):
    """Individual answer in a quiz attempt"""
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answer = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'), ('', 'Not Answered')], blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.attempt.user.username} - Q{self.question.id}"

class Content(models.Model):
    """Learning content (PDF files)"""
    CONTENT_TYPE_CHOICES = [
        ('pdf', 'PDF Document'),
        ('other', 'Other'),
    ]
    
    title = models.CharField(max_length=300, db_index=True)
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to='content/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES, default='pdf')
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, related_name='contents', null=True, blank=True)
    standard = models.ForeignKey(Standard, on_delete=models.SET_NULL, related_name='contents', null=True, blank=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='contents', null=True, blank=True, db_index=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_content')
    is_public = models.BooleanField(default=True, help_text="Visible to all users if public")
    view_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'is_public']),
            models.Index(fields=['subject', 'standard']),
        ]

    def __str__(self):
        return self.title

class QuestionUpload(models.Model):
    """Word file upload for bulk question import"""
    file = models.FileField(
        upload_to='question_uploads/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['docx'])]
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    standard = models.ForeignKey(Standard, on_delete=models.CASCADE)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    questions_imported = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file.name} - {self.subject.name}"