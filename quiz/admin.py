from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils.html import format_html

from .models import (
    Institution, UserProfile, ActivityLog, Subject, Standard,
    Question, MarkingScheme, Quiz, QuizAttempt, Answer,
    Content, QuestionUpload
)
from .forms import QuestionUploadForm
from .utils import parse_question_from_docx, log_activity

# Unregister default User admin
admin.site.unregister(User)

# Inline for UserProfile
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile Information'
    fields = (
        'role', 'institution',
        'student_name', 'roll_number',
        'can_create_quiz', 'can_upload_content'
    )
    
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ['can_create_quiz', 'can_upload_content']
        return []

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Enhanced user admin with profile inline"""
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'get_role', 'get_institution', 'is_active', 'is_staff', 'date_joined']
    list_filter = ['is_active', 'is_staff', 'date_joined', 'profile__role', 'profile__institution']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'profile__student_name', 'profile__roll_number']
    list_per_page = 25
    
    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return format_html(
                '<span class="badge badge-info">{}</span>',
                obj.profile.get_role_display()
            )
        return 'N/A'
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'profile__role'
    
    def get_institution(self, obj):
        if hasattr(obj, 'profile') and obj.profile.institution:
            return obj.profile.institution.name
        return 'N/A'
    get_institution.short_description = 'Institution'
    get_institution.admin_order_field = 'profile__institution'
    
    def save_model(self, request, obj, form, change):
        if not change:
            log_activity(request.user, 'user_create', f'Created user: {obj.username}', request)
        else:
            log_activity(request.user, 'user_update', f'Updated user: {obj.username}', request)
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(profile__institution=request.user.profile.institution)
        return qs.none()

@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Institution management"""
    list_display = ['name', 'code', 'is_active', 'user_count', 'quiz_count', 'content_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'code', 'contact_email']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Contact Details', {
            'fields': ('address', 'contact_email', 'contact_phone')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_count(self, obj):
        count = obj.users.count()
        return format_html('<strong>{}</strong>', count)
    user_count.short_description = 'Users'
    
    def quiz_count(self, obj):
        count = obj.quizzes.count()
        return format_html('<strong>{}</strong>', count)
    quiz_count.short_description = 'Quizzes'
    
    def content_count(self, obj):
        count = obj.contents.count()
        return format_html('<strong>{}</strong>', count)
    content_count.short_description = 'Content'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(id=request.user.profile.institution.id)
        return qs.none()
    
    def has_add_permission(self, request):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User profile management"""
    list_display = ['user', 'role', 'institution', 'student_name', 'roll_number', 'can_create_quiz', 'can_upload_content']
    list_filter = ['role', 'institution', 'can_create_quiz', 'can_upload_content']
    search_fields = ['user__username', 'student_name', 'roll_number']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('User Association', {
            'fields': ('user', 'role', 'institution')
        }),
        ('Student Information', {
            'fields': ('student_name', 'roll_number'),
            'classes': ('collapse',)
        }),
        ('Teacher Permissions', {
            'fields': ('can_create_quiz', 'can_upload_content'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(institution=request.user.profile.institution)
        return qs.none()

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Activity log viewer"""
    list_display = ['user', 'action', 'description_short', 'ip_address', 'timestamp']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'description', 'ip_address']
    readonly_fields = ['user', 'action', 'description', 'ip_address', 'timestamp']
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    def description_short(self, obj):
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Description'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(user__profile__institution=request.user.profile.institution)
        return qs.none()

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Subject management"""
    list_display = ['name', 'question_count', 'quiz_count', 'created_at']
    search_fields = ['name', 'description']
    list_per_page = 25
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    def quiz_count(self, obj):
        return obj.quizzes.count()
    quiz_count.short_description = 'Quizzes'

@admin.register(Standard)
class StandardAdmin(admin.ModelAdmin):
    """Standard/Class management"""
    list_display = ['name', 'is_miscellaneous', 'question_count', 'quiz_count', 'created_at']
    list_filter = ['is_miscellaneous']
    search_fields = ['name', 'description']
    list_per_page = 25
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Questions'
    
    def quiz_count(self, obj):
        return obj.quizzes.count()
    quiz_count.short_description = 'Quizzes'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Question bank management"""
    list_display = ['question_short', 'subject', 'standard', 'institution', 'correct_answer', 'created_by', 'created_at']
    list_filter = ['subject', 'standard', 'institution', 'correct_answer', 'created_at']
    search_fields = ['question_text']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    list_per_page = 20
    
    fieldsets = (
        ('Question Details', {
            'fields': ('subject', 'standard', 'institution', 'question_text')
        }),
        ('Options', {
            'fields': ('option_a', 'option_b', 'option_c', 'option_d', 'correct_answer')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_short(self, obj):
        return obj.question_text[:60] + '...' if len(obj.question_text) > 60 else obj.question_text
    question_short.short_description = 'Question'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            if hasattr(request.user, 'profile'):
                obj.institution = request.user.profile.institution
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(Q(institution=request.user.profile.institution) | Q(institution__isnull=True))
        return qs.none()

@admin.register(MarkingScheme)
class MarkingSchemeAdmin(admin.ModelAdmin):
    """Marking scheme management"""
    list_display = ['name', 'correct_marks', 'wrong_marks', 'quiz_count', 'created_at']
    search_fields = ['name']
    list_per_page = 25
    
    def quiz_count(self, obj):
        return obj.quizzes.count()
    quiz_count.short_description = 'Quizzes Using'

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Quiz management"""
    list_display = ['title', 'subject', 'standard', 'institution', 'marking_scheme', 'question_count', 'duration_minutes', 'is_active', 'attempt_count', 'created_at']
    list_filter = ['subject', 'standard', 'institution', 'is_active', 'created_at']
    search_fields = ['title', 'description']
    filter_horizontal = ['questions']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'subject', 'standard', 'institution')
        }),
        ('Quiz Settings', {
            'fields': ('marking_scheme', 'duration_minutes', 'is_active')
        }),
        ('Questions', {
            'fields': ('questions',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_count(self, obj):
        count = obj.questions.count()
        return format_html('<strong>{}</strong>', count)
    question_count.short_description = 'Questions'
    
    def attempt_count(self, obj):
        count = obj.attempts.count()
        return format_html('<strong>{}</strong>', count)
    attempt_count.short_description = 'Attempts'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            if hasattr(request.user, 'profile'):
                obj.institution = request.user.profile.institution
            log_activity(request.user, 'quiz_create', f'Created quiz: {obj.title}', request)
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(institution=request.user.profile.institution)
        return qs.none()
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.can_create_quiz or request.user.profile.role in ['principal']
        return False
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "questions":
            if hasattr(request.user, 'profile') and request.user.profile.institution:
                kwargs["queryset"] = Question.objects.filter(
                    Q(institution=request.user.profile.institution) | Q(institution__isnull=True)
                )
        return super().formfield_for_manytomany(db_field, request, **kwargs)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Quiz attempt records"""
    list_display = ['user', 'get_student_name', 'get_roll_number', 'quiz', 'score', 'percentage_display', 'correct_answers', 'wrong_answers', 'started_at']
    list_filter = ['quiz', 'started_at', 'quiz__subject', 'quiz__standard', 'user__profile__institution']
    search_fields = ['user__username', 'user__profile__student_name', 'user__profile__roll_number', 'quiz__title']
    readonly_fields = ['user', 'quiz', 'score', 'total_questions', 'correct_answers', 'wrong_answers', 'unanswered', 'started_at', 'completed_at']
    date_hierarchy = 'started_at'
    list_per_page = 50
    
    def get_student_name(self, obj):
        return obj.user.profile.student_name if hasattr(obj.user, 'profile') else 'N/A'
    get_student_name.short_description = 'Student Name'
    
    def get_roll_number(self, obj):
        return obj.user.profile.roll_number if hasattr(obj.user, 'profile') else 'N/A'
    get_roll_number.short_description = 'Roll Number'
    
    def percentage_display(self, obj):
        return f"{obj.percentage}%"
    percentage_display.short_description = 'Percentage'
    
    def has_add_permission(self, request):
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(quiz__institution=request.user.profile.institution)
        return qs.none()

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Individual answer records"""
    list_display = ['attempt_info', 'question_short', 'selected_answer', 'is_correct']
    list_filter = ['is_correct', 'attempt__quiz']
    readonly_fields = ['attempt', 'question', 'selected_answer', 'is_correct']
    list_per_page = 100
    
    def attempt_info(self, obj):
        return f"{obj.attempt.user.username} - {obj.attempt.quiz.title}"
    attempt_info.short_description = 'Attempt'
    
    def question_short(self, obj):
        return obj.question.question_text[:40] + '...'
    question_short.short_description = 'Question'
    
    def has_add_permission(self, request):
        return False

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    """Learning content management"""
    list_display = ['title', 'content_type', 'subject', 'standard', 'institution', 'uploaded_by', 'is_public', 'view_count', 'created_at']
    list_filter = ['content_type', 'subject', 'standard', 'institution', 'is_public', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['uploaded_by', 'view_count', 'created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Content Information', {
            'fields': ('title', 'description', 'file', 'content_type')
        }),
        ('Classification', {
            'fields': ('subject', 'standard', 'institution', 'is_public')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
            if hasattr(request.user, 'profile') and not obj.institution:
                obj.institution = request.user.profile.institution
            log_activity(request.user, 'content_upload', f'Uploaded: {obj.title}', request)
        super().save_model(request, obj, form, change)
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.can_upload_content or request.user.profile.role in ['principal']
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(Q(institution=request.user.profile.institution) | Q(is_public=True))
        return qs.filter(is_public=True)

@admin.register(QuestionUpload)
class QuestionUploadAdmin(admin.ModelAdmin):
    """Question file upload management"""
    list_display = ['file_name', 'subject', 'standard', 'institution', 'uploaded_by', 'uploaded_at', 'processed', 'questions_imported']
    list_filter = ['processed', 'subject', 'standard', 'institution', 'uploaded_at']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'processed', 'questions_imported', 'error_message']
    list_per_page = 25
    
    def file_name(self, obj):
        return obj.file.name.split('/')[-1]
    file_name.short_description = 'File'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-questions/', self.admin_site.admin_view(self.upload_questions_view), name='quiz_upload_questions'),
        ]
        return custom_urls + urls
    
    def upload_questions_view(self, request):
        if request.method == 'POST':
            form = QuestionUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.save(commit=False)
                upload.uploaded_by = request.user
                if hasattr(request.user, 'profile'):
                    upload.institution = request.user.profile.institution
                upload.save()
                
                try:
                    questions_data = parse_question_from_docx(upload.file.path)
                    
                    for q_data in questions_data:
                        correct_option = None
                        options_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
                        
                        for idx, opt in enumerate(q_data['options']):
                            option_letter = chr(65 + idx)
                            options_dict[option_letter] = opt['text']
                            if opt['is_correct']:
                                correct_option = option_letter
                        
                        if correct_option:
                            Question.objects.create(
                                subject=upload.subject,
                                standard=upload.standard,
                                institution=upload.institution,
                                created_by=request.user,
                                question_text=q_data['question'],
                                option_a=options_dict['A'],
                                option_b=options_dict['B'],
                                option_c=options_dict['C'],
                                option_d=options_dict['D'],
                                correct_answer=correct_option
                            )
                    
                    upload.processed = True
                    upload.questions_imported = len(questions_data)
                    upload.save()
                    
                    messages.success(request, f'Successfully imported {len(questions_data)} questions!')
                    return redirect('admin:quiz_questionupload_changelist')
                
                except Exception as e:
                    upload.error_message = str(e)
                    upload.save()
                    messages.error(request, f'Error processing file: {str(e)}')
        else:
            form = QuestionUploadForm()
        
        return render(request, 'admin/quiz/upload_questions.html', {'form': form, 'title': 'Upload Questions'})
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploaded_by = request.user
            if hasattr(request.user, 'profile'):
                obj.institution = request.user.profile.institution
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(institution=request.user.profile.institution)
        return qs.none()

# Admin Site Customization
admin.site.site_header = "Quiz Platform Administration"
admin.site.site_title = "Quiz Platform"
admin.site.index_title = "Dashboard"
