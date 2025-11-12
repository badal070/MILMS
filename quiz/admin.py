from django.contrib import admin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils.html import format_html
from .forms import QuestionUploadForm
from .utils import (
    parse_question_from_docx, 
    parse_question_from_pdf,
    validate_questions,
    preview_parsed_questions,
    log_activity)
from .descriptive_evaluation import evaluate_descriptive_answer
from .models import (
    Institution, UserProfile, ActivityLog, Subject, Standard,
    Question, MarkingScheme, Quiz, QuizAttempt, Answer,
    Content, QuestionUpload,DescriptiveQuestion, DescriptiveQuiz, DescriptiveQuizAttempt,
    DescriptiveAnswer, DescriptiveQuestionUpload, AIEvaluationLog
)
from .forms import QuestionUploadForm
from .utils import parse_question_from_docx, log_activity
import traceback

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
    
    """Enhanced Question Upload with Complete Workflow"""
    
    list_display = [
        'file_name', 'file_type_badge', 'subject', 'standard', 
        'institution', 'uploaded_by', 'uploaded_at', 'status_display', 
        'questions_imported', 'action_buttons'
    ]
    list_filter = ['processed', 'subject', 'standard', 'institution', 'uploaded_at']
    search_fields = ['file', 'subject__name', 'standard__name', 'uploaded_by__username']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'processed', 'questions_imported', 'error_message', 'preview_info']
    list_per_page = 25
    
    fieldsets = (
        ('File Information', {
            'fields': ('file', 'subject', 'standard')
        }),
        ('Upload Details', {
            'fields': ('uploaded_by', 'uploaded_at', 'institution'),
            'classes': ('collapse',)
        }),
        ('Processing Status', {
            'fields': ('processed', 'questions_imported', 'error_message'),
            'classes': ('collapse',)
        }),
    )
    
    def file_name(self, obj):
        """Display file name"""
        if obj.file:
            name = obj.file.name.split('/')[-1]
            return name if len(name) < 40 else name[:37] + '...'
        return 'N/A'
    file_name.short_description = 'File Name'
    
    def file_type_badge(self, obj):
        """Display file type with colored badge"""
        if not obj.file:
            return format_html('<span style="color: #999;">N/A</span>')
        
        ext = obj.file.name.split('.')[-1].upper()
        colors = {
            'DOCX': '#667eea',
            'PDF': '#dc3545',
        }
        color = colors.get(ext, '#6c757d')
        
        return format_html(
            '<span style="background: {}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600;">{}</span>',
            color, ext
        )
    file_type_badge.short_description = 'Type'
    
    def status_display(self, obj):
        """Display processing status with badge"""
        if obj.processed:
            if obj.questions_imported > 0:
                return format_html(
                    '<span style="background: #10b981; color: white; padding: 5px 12px; border-radius: 4px; font-weight: 600;">✓ Imported</span>'
                )
            else:
                return format_html(
                    '<span style="background: #f59e0b; color: white; padding: 5px 12px; border-radius: 4px; font-weight: 600;">⚠ Failed</span>'
                )
        else:
            return format_html(
                '<span style="background: #3b82f6; color: white; padding: 5px 12px; border-radius: 4px; font-weight: 600;">⏳ Pending</span>'
            )
    status_display.short_description = 'Status'
    
    def action_buttons(self, obj):
        """Display action buttons"""
        if not obj.processed:
            preview_url = reverse('admin:quiz_preview_upload', args=[obj.id])
            return format_html(
                '<a href="{}" class="button" style="background: #667eea; color: white; padding: 6px 14px; text-decoration: none; border-radius: 4px; font-size: 12px; font-weight: 600;">Preview & Import</a>',
                preview_url
            )
        elif obj.questions_imported > 0:
            return format_html(
                '<span style="color: #10b981; font-weight: 600;">✓ {} questions imported</span>',
                obj.questions_imported
            )
        else:
            return format_html(
                '<span style="color: #f59e0b; font-weight: 600;">⚠ Import failed</span>'
            )
    action_buttons.short_description = 'Actions'
    
    def preview_info(self, obj):
        """Show preview information in detail view"""
        if obj.processed:
            if obj.questions_imported > 0:
                return format_html(
                    '<div style="background: #f0fdf4; border: 2px solid #10b981; padding: 15px; border-radius: 8px;">'
                    '<strong style="color: #047857;">✓ Successfully Imported</strong><br>'
                    '<span style="color: #065f46;">Questions imported: {}</span>'
                    '</div>',
                    obj.questions_imported
                )
            else:
                return format_html(
                    '<div style="background: #fef2f2; border: 2px solid #ef4444; padding: 15px; border-radius: 8px;">'
                    '<strong style="color: #991b1b;">✗ Import Failed</strong><br>'
                    '<span style="color: #7f1d1d;">{}</span>'
                    '</div>',
                    obj.error_message or 'No questions found in file'
                )
        else:
            preview_url = reverse('admin:quiz_preview_upload', args=[obj.id])
            return format_html(
                '<div style="background: #eff6ff; border: 2px solid #3b82f6; padding: 15px; border-radius: 8px;">'
                '<strong style="color: #1e40af;">⏳ Pending Import</strong><br>'
                '<a href="{}" style="color: #2563eb; font-weight: 600;">Click here to preview and import questions</a>'
                '</div>',
                preview_url
            )
    preview_info.short_description = 'Import Status'
    
    def get_urls(self):
        """Register custom URLs"""
        urls = super().get_urls()
        custom_urls = [
            path(
                'upload-questions/',
                self.admin_site.admin_view(self.upload_questions_view),
                name='quiz_upload_questions'
            ),
            path(
                '<int:upload_id>/preview/',
                self.admin_site.admin_view(self.preview_upload_view),
                name='quiz_preview_upload'
            ),
            path(
                '<int:upload_id>/process/',
                self.admin_site.admin_view(self.process_upload_view),
                name='quiz_process_upload'
            ),
        ]
        return custom_urls + urls
    
    def upload_questions_view(self, request):
        """Step 1: Upload File View"""
        if request.method == 'POST':
            form = QuestionUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    upload = form.save(commit=False)
                    upload.uploaded_by = request.user
                    
                    # Set institution
                    if hasattr(request.user, 'profile') and request.user.profile.institution:
                        upload.institution = request.user.profile.institution
                    
                    upload.save()
                    
                    # Log activity
                    log_activity(
                        request.user, 
                        'content_upload', 
                        f'Uploaded question file: {upload.file.name}',
                        request
                    )
                    
                    messages.success(request, f'File uploaded successfully! Now previewing questions...')
                    return redirect('admin:quiz_preview_upload', upload_id=upload.id)
                    
                except Exception as e:
                    messages.error(request, f'Upload failed: {str(e)}')
                    print(f"Upload error: {traceback.format_exc()}")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        else:
            form = QuestionUploadForm()
        
        context = {
            'form': form,
            'title': 'Upload Questions from File',
            'site_title': 'Quiz Platform',
            'site_header': 'Quiz Platform Administration',
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        return render(request, 'admin/quiz/upload_questions.html', context)
    
    def preview_upload_view(self, request, upload_id):
        """Step 2: Preview Parsed Questions"""
        upload = get_object_or_404(QuestionUpload, id=upload_id)
        
        # Check if already processed
        if upload.processed:
            messages.info(request, 'This file has already been processed.')
            if upload.questions_imported > 0:
                messages.success(request, f'{upload.questions_imported} questions were imported.')
            return redirect('admin:quiz_questionupload_change', upload.id)
        
        try:
            # Parse questions based on file type
            file_ext = upload.file.name.split('.')[-1].lower()
            
            print(f"Parsing file: {upload.file.path}")
            print(f"File type: {file_ext}")
            
            if file_ext == 'docx':
                questions = parse_question_from_docx(upload.file.path)
            elif file_ext == 'pdf':
                questions = parse_question_from_pdf(upload.file.path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}. Only .docx and .pdf are supported.")
            
            print(f"Parsed {len(questions)} questions")
            
            # Validate questions
            is_valid, errors = validate_questions(questions)
            
            # Generate preview text
            preview_text = preview_parsed_questions(questions, max_questions=5)
            
            context = {
                'upload': upload,
                'questions': questions,
                'question_count': len(questions),
                'is_valid': is_valid,
                'errors': errors,
                'preview_text': preview_text,
                'title': f'Preview: {upload.file.name.split("/")[-1]}',
                'site_title': 'Quiz Platform',
                'site_header': 'Quiz Platform Administration',
                'opts': self.model._meta,
                'has_view_permission': True,
            }
            
            return render(request, 'admin/quiz/preview_questions.html', context)
            
        except Exception as e:
            error_msg = str(e)
            print(f"Preview error: {traceback.format_exc()}")
            
            upload.error_message = error_msg
            upload.processed = True  # Mark as processed with error
            upload.save()
            
            messages.error(request, f'Error parsing file: {error_msg}')
            return redirect('admin:quiz_questionupload_change', upload.id)
    
    def process_upload_view(self, request, upload_id):
        """Step 3: Import Questions into Database"""
        upload = get_object_or_404(QuestionUpload, id=upload_id)
        
        # Check if already processed
        if upload.processed:
            messages.warning(request, 'This file has already been processed.')
            return redirect('admin:quiz_questionupload_changelist')
        
        try:
            # Parse questions again
            file_ext = upload.file.name.split('.')[-1].lower()
            
            print(f"Processing file: {upload.file.path}")
            
            if file_ext == 'docx':
                questions_data = parse_question_from_docx(upload.file.path)
            elif file_ext == 'pdf':
                questions_data = parse_question_from_pdf(upload.file.path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            print(f"Parsed {len(questions_data)} questions for import")
            
            # Import questions into database
            imported_count = 0
            skipped_count = 0
            error_details = []
            
            for idx, q_data in enumerate(questions_data, 1):
                try:
                    # Map options to A, B, C, D
                    correct_option = None
                    options_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
                    
                    # Process options
                    for opt_idx, opt in enumerate(q_data['options'][:4]):
                        letters = ['A', 'B', 'C', 'D']
                        option_letter = letters[opt_idx] if opt_idx < len(letters) else '?'
                        options_dict[option_letter] = opt['text'][:500]
                        if opt['is_correct']:
                            correct_option = option_letter

                    
                    # Validate before saving
                    if not correct_option:
                        skipped_count += 1
                        error_details.append(f"Question {idx}: No correct answer marked")
                        continue
                    
                    if not q_data['question']:
                        skipped_count += 1
                        error_details.append(f"Question {idx}: Empty question text")
                        continue
                    
                    # Create question
                    question = Question.objects.create(
                        subject=upload.subject,
                        standard=upload.standard,
                        institution=upload.institution,
                        created_by=request.user,
                        question_text=q_data['question'][:1000],  # Limit length
                        option_a=options_dict['A'],
                        option_b=options_dict['B'],
                        option_c=options_dict['C'],
                        option_d=options_dict['D'],
                        correct_answer=correct_option
                    )
                    
                    imported_count += 1
                    print(f"Imported question {idx}: {question.id}")
                    
                except Exception as e:
                    skipped_count += 1
                    error_msg = f"Question {idx}: {str(e)}"
                    error_details.append(error_msg)
                    print(f"Error importing question {idx}: {str(e)}")
            
            # Update upload record
            upload.processed = True
            upload.questions_imported = imported_count
            
            if error_details:
                upload.error_message = f"Imported {imported_count}, Skipped {skipped_count}. Errors: " + "; ".join(error_details[:5])
            
            upload.save()
            
            print(f"Final status - Imported: {imported_count}, Skipped: {skipped_count}")
            
            # Log activity
            log_activity(
                request.user,
                'quiz_create',
                f'Imported {imported_count} questions from {upload.file.name}',
                request
            )
            
            # Show results
            if imported_count > 0:
                messages.success(
                    request,
                    f'✓ Successfully imported {imported_count} question(s)! '
                    f'{f"({skipped_count} skipped due to errors)" if skipped_count > 0 else ""}'
                )
            else:
                messages.error(
                    request,
                    f'✗ No questions were imported. {skipped_count} question(s) had errors. '
                    'Please check the file format and try again.'
                )
            
            if error_details:
                for error in error_details[:5]:  # Show first 5 errors
                    messages.warning(request, error)
            
            return redirect('admin:quiz_questionupload_changelist')
            
        except Exception as e:
            error_msg = str(e)
            print(f"Process error: {traceback.format_exc()}")
            
            upload.processed = True
            upload.questions_imported = 0
            upload.error_message = f"Critical error: {error_msg}"
            upload.save()
            
            messages.error(request, f'✗ Import failed: {error_msg}')
            return redirect('admin:quiz_questionupload_changelist')
    
    def save_model(self, request, obj, form, change):
        """Save model with user information"""
        if not change:
            obj.uploaded_by = request.user
            if hasattr(request.user, 'profile') and request.user.profile.institution:
                obj.institution = request.user.profile.institution
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Filter queryset by institution"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(institution=request.user.profile.institution)
        return qs.none()
    
    def has_add_permission(self, request):
        """Check if user can add uploads"""
        return request.user.is_superuser or (
            hasattr(request.user, 'profile') and
            request.user.profile.role in ['teacher', 'principal']
        )
    
    def has_delete_permission(self, request, obj=None):
        """Check if user can delete uploads"""
        if request.user.is_superuser:
            return True
        if obj and hasattr(request.user, 'profile'):
            return obj.institution == request.user.profile.institution
        return False
    
    def changelist_view(self, request, extra_context=None):
        """Add custom context to changelist"""
        extra_context = extra_context or {}
        extra_context['show_upload_button'] = True
        return super().changelist_view(request, extra_context=extra_context)

@admin.register(DescriptiveQuestion)
class DescriptiveQuestionAdmin(admin.ModelAdmin):
    """Admin interface for descriptive questions"""
    list_display = [
        'question_preview', 'subject', 'standard', 'institution',
        'max_marks', 'word_limit', 'enable_ai_evaluation', 
        'is_active', 'created_by', 'created_at'
    ]
    list_filter = [
        'subject', 'standard', 'institution', 'enable_ai_evaluation',
        'is_active', 'created_at'
    ]
    search_fields = ['question_text', 'reference_answer', 'marking_guidelines']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    list_per_page = 20
    
    fieldsets = (
        ('Question Details', {
            'fields': ('subject', 'standard', 'institution', 'question_text')
        }),
        ('Reference & Guidelines', {
            'fields': ('reference_answer', 'marking_guidelines')
        }),
        ('Marking Settings', {
            'fields': ('max_marks', 'word_limit')
        }),
        ('AI Evaluation Settings', {
            'fields': ('enable_ai_evaluation', 'ai_evaluation_weightage'),
            'classes': ('collapse',)
        }),
        ('Status & Metadata', {
            'fields': ('is_active', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def question_preview(self, obj):
        preview = obj.question_text[:80] + '...' if len(obj.question_text) > 80 else obj.question_text
        return format_html('<span title="{}">{}</span>', obj.question_text, preview)
    question_preview.short_description = 'Question'
    
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
            return qs.filter(
                Q(institution=request.user.profile.institution) | 
                Q(institution__isnull=True)
            )
        return qs.none()
    
    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.role in ['teacher', 'principal']
        return False


# ==================== DESCRIPTIVE QUIZ ADMIN ====================

@admin.register(DescriptiveQuiz)
class DescriptiveQuizAdmin(admin.ModelAdmin):
    """Admin interface for descriptive quizzes"""
    list_display = [
        'title', 'subject', 'standard', 'institution',
        'question_count', 'total_marks_display', 'duration_minutes',
        'auto_evaluate', 'is_active', 'attempt_count', 'created_at'
    ]
    list_filter = [
        'subject', 'standard', 'institution', 'auto_evaluate',
        'require_manual_review', 'is_active', 'created_at'
    ]
    search_fields = ['title', 'description']
    filter_horizontal = ['questions']
    readonly_fields = ['created_by', 'created_at', 'updated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'subject', 'standard', 'institution')
        }),
        ('Quiz Settings', {
            'fields': ('duration_minutes', 'is_active')
        }),
        ('Questions', {
            'fields': ('questions',)
        }),
        ('Evaluation Settings', {
            'fields': ('auto_evaluate', 'require_manual_review'),
            'classes': ('collapse',)
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
    
    def total_marks_display(self, obj):
        return format_html('<strong>{}</strong> marks', obj.total_marks)
    total_marks_display.short_description = 'Total Marks'
    
    def attempt_count(self, obj):
        count = obj.attempts.count()
        return format_html('<strong>{}</strong>', count)
    attempt_count.short_description = 'Attempts'
    
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
                kwargs["queryset"] = DescriptiveQuestion.objects.filter(
                    Q(institution=request.user.profile.institution) | 
                    Q(institution__isnull=True),
                    is_active=True
                )
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# ==================== DESCRIPTIVE QUIZ ATTEMPT ADMIN ====================

@admin.register(DescriptiveQuizAttempt)
class DescriptiveQuizAttemptAdmin(admin.ModelAdmin):
    """Admin interface for viewing and reviewing attempts"""
    list_display = [
        'user_info', 'quiz', 'status_badge', 'final_score',
        'total_marks', 'percentage_display', 'submitted_at',
        'review_actions'
    ]
    list_filter = [
        'status', 'quiz__subject', 'quiz__standard',
        'quiz__institution', 'submitted_at'
    ]
    search_fields = [
        'user__username', 'user__profile__student_name',
        'user__profile__roll_number', 'quiz__title'
    ]
    readonly_fields = [
        'user', 'quiz', 'started_at', 'submitted_at',
        'ai_evaluated_at', 'manually_reviewed_at', 'finalized_at',
        'ai_score', 'manual_score', 'final_score', 'total_marks'
    ]
    date_hierarchy = 'submitted_at'
    list_per_page = 50
    
    fieldsets = (
        ('Attempt Information', {
            'fields': ('user', 'quiz', 'status')
        }),
        ('Scores', {
            'fields': ('ai_score', 'manual_score', 'final_score', 'total_marks')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'teacher_comments')
        }),
        ('Timestamps', {
            'fields': (
                'started_at', 'submitted_at', 'ai_evaluated_at',
                'manually_reviewed_at', 'finalized_at'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['trigger_ai_evaluation', 'finalize_attempts']
    
    def user_info(self, obj):
        if hasattr(obj.user, 'profile'):
            return format_html(
                '<strong>{}</strong><br><small>{}</small>',
                obj.user.profile.display_name,
                obj.user.username
            )
        return obj.user.username
    user_info.short_description = 'Student'
    
    def status_badge(self, obj):
        colors = {
            'draft': 'secondary',
            'submitted': 'info',
            'ai_evaluated': 'warning',
            'manually_reviewed': 'primary',
            'finalized': 'success'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def percentage_display(self, obj):
        return format_html('{}%', obj.percentage)
    percentage_display.short_description = 'Percentage'
    
    def review_actions(self, obj):
        if obj.status in ['submitted', 'ai_evaluated']:
            url = f'/admin/quiz/descriptivequizattempt/{obj.id}/review/'
            return format_html(
                '<a class="button" href="{}">Review</a>',
                url
            )
        return '-'
    review_actions.short_description = 'Actions'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:attempt_id>/review/',
                self.admin_site.admin_view(self.review_attempt_view),
                name='descriptive_attempt_review'
            ),
        ]
        return custom_urls + urls
    
    def review_attempt_view(self, request, attempt_id):
        """Custom view for reviewing descriptive attempts"""
        from django.shortcuts import get_object_or_404
        
        attempt = get_object_or_404(DescriptiveQuizAttempt, id=attempt_id)
        answers = attempt.answers.select_related('question').all()
        
        if request.method == 'POST':
            # Process manual scores
            for answer in answers:
                score_key = f'score_{answer.id}'
                feedback_key = f'feedback_{answer.id}'
                
                if score_key in request.POST:
                    try:
                        manual_score = float(request.POST[score_key])
                        answer.manual_score = manual_score
                        answer.manual_feedback = request.POST.get(feedback_key, '')
                        
                        # Calculate final score
                        if answer.ai_score and answer.question.enable_ai_evaluation:
                            weight = float(answer.question.ai_evaluation_weightage)
                            answer.final_score = (
                                answer.ai_score * weight +
                                manual_score * (1 - weight)
                            )
                        else:
                            answer.final_score = manual_score
                        
                        answer.save()
                    except ValueError:
                        pass
            
            # Update attempt
            attempt.manual_score = sum(a.manual_score or 0 for a in answers)
            attempt.final_score = sum(a.final_score for a in answers)
            attempt.status = 'manually_reviewed'
            attempt.reviewed_by = request.user
            attempt.manually_reviewed_at = timezone.now()
            attempt.teacher_comments = request.POST.get('teacher_comments', '')
            attempt.save()
            
            messages.success(request, f'Review saved for {attempt.user.username}')
            return redirect('admin:quiz_descriptivequizattempt_changelist')
        
        context = {
            'attempt': attempt,
            'answers': answers,
            'title': f'Review: {attempt.quiz.title} - {attempt.user.username}',
            'opts': self.model._meta,
            'has_view_permission': True,
        }
        
        return render(request, 'admin/quiz/review_descriptive_attempt.html', context)
    
    def trigger_ai_evaluation(self, request, queryset):
        """Bulk action to trigger AI evaluation"""
        from .descriptive_evaluation import evaluate_descriptive_answer
        
        api_key = os.getenv('HUGGINGFACE_API_KEY')
        if not api_key:
            self.message_user(
                request,
                'HUGGINGFACE_API_KEY not configured in environment',
                messages.ERROR
            )
            return
        
        evaluated = 0
        for attempt in queryset.filter(status='submitted'):
            try:
                for answer in attempt.answers.all():
                    result = evaluate_descriptive_answer(
                        api_key=api_key,
                        question=answer.question.question_text,
                        user_answer=answer.answer_text,
                        standard_answer=answer.question.reference_answer,
                        max_score=answer.question.max_marks
                    )
                    
                    # Save evaluation results
                    answer.ai_score = result['overall_score']
                    answer.ai_evaluation_data = result
                    answer.ai_feedback = result['feedback']
                    answer.spelling_score = result['spelling_analysis'].get('spelling_score', 0)
                    answer.relevance_score = result['relevance_analysis'].get('relevance_score', 0)
                    answer.content_score = result['content_analysis'].get('content_score', 0)
                    answer.grammar_score = result['grammar_analysis'].get('grammar_score', 0)
                    answer.final_score = answer.ai_score
                    answer.save()
                
                # Update attempt
                attempt.ai_score = sum(a.ai_score for a in attempt.answers.all())
                attempt.final_score = attempt.ai_score
                attempt.status = 'ai_evaluated'
                attempt.ai_evaluated_at = timezone.now()
                attempt.save()
                
                evaluated += 1
            except Exception as e:
                messages.error(request, f'Error evaluating {attempt}: {str(e)}')
        
        self.message_user(
            request,
            f'{evaluated} attempt(s) evaluated successfully',
            messages.SUCCESS
        )
    
    trigger_ai_evaluation.short_description = "Trigger AI Evaluation"
    
    def finalize_attempts(self, request, queryset):
        """Finalize reviewed attempts"""
        count = queryset.filter(
            status__in=['ai_evaluated', 'manually_reviewed']
        ).update(
            status='finalized',
            finalized_at=timezone.now()
        )
        self.message_user(
            request,
            f'{count} attempt(s) finalized',
            messages.SUCCESS
        )
    
    finalize_attempts.short_description = "Finalize Attempts"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(quiz__institution=request.user.profile.institution)
        return qs.none()
    
    def has_add_permission(self, request):
        return False


# ==================== DESCRIPTIVE ANSWER ADMIN ====================

@admin.register(DescriptiveAnswer)
class DescriptiveAnswerAdmin(admin.ModelAdmin):
    """Admin for individual answers"""
    list_display = [
        'attempt_info', 'question_preview', 'word_count',
        'ai_score', 'manual_score', 'final_score', 'created_at'
    ]
    list_filter = ['attempt__quiz', 'attempt__status', 'created_at']
    search_fields = [
        'attempt__user__username', 'question__question_text',
        'answer_text'
    ]
    readonly_fields = [
        'attempt', 'question', 'word_count', 'created_at',
        'updated_at', 'ai_evaluation_data'
    ]
    list_per_page = 50
    
    fieldsets = (
        ('Answer Information', {
            'fields': ('attempt', 'question', 'answer_text', 'word_count')
        }),
        ('AI Evaluation', {
            'fields': (
                'ai_score', 'ai_feedback', 'spelling_score',
                'relevance_score', 'content_score', 'grammar_score',
                'ai_evaluation_data'
            ),
            'classes': ('collapse',)
        }),
        ('Manual Evaluation', {
            'fields': ('manual_score', 'manual_feedback')
        }),
        ('Final Score', {
            'fields': ('final_score',)
        }),
    )
    
    def attempt_info(self, obj):
        return f"{obj.attempt.user.username} - {obj.attempt.quiz.title}"
    attempt_info.short_description = 'Attempt'
    
    def question_preview(self, obj):
        return obj.question.question_text[:50] + '...'
    question_preview.short_description = 'Question'
    
    def has_add_permission(self, request):
        return False


# ==================== DESCRIPTIVE QUESTION UPLOAD ADMIN ====================

@admin.register(DescriptiveQuestionUpload)
class DescriptiveQuestionUploadAdmin(admin.ModelAdmin):
    """Admin for bulk uploading descriptive questions"""
    list_display = [
        'file_name', 'subject', 'standard', 'institution',
        'uploaded_by', 'uploaded_at', 'processed', 'questions_imported'
    ]
    list_filter = ['processed', 'subject', 'standard', 'institution', 'uploaded_at']
    readonly_fields = [
        'uploaded_by', 'uploaded_at', 'processed',
        'questions_imported', 'error_message'
    ]
    list_per_page = 25
    
    def file_name(self, obj):
        return obj.file.name.split('/')[-1]
    file_name.short_description = 'File'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'upload-descriptive/',
                self.admin_site.admin_view(self.upload_view),
                name='upload_descriptive_questions'
            ),
        ]
        return custom_urls + urls
    
    def upload_view(self, request):
        """Custom upload view"""
        if request.method == 'POST':
            form = DescriptiveQuestionUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.save(commit=False)
                upload.uploaded_by = request.user
                if hasattr(request.user, 'profile'):
                    upload.institution = request.user.profile.institution
                upload.save()
                
                try:
                    questions_data = parse_descriptive_questions_from_docx(
                        upload.file.path
                    )
                    
                    for q_data in questions_data:
                        DescriptiveQuestion.objects.create(
                            subject=upload.subject,
                            standard=upload.standard,
                            institution=upload.institution,
                            created_by=request.user,
                            question_text=q_data['question'],
                            reference_answer=q_data.get('reference_answer', ''),
                            marking_guidelines=q_data.get('marking_guidelines', ''),
                            max_marks=q_data.get('max_marks', 10),
                            word_limit=q_data.get('word_limit', 500)
                        )
                    
                    upload.processed = True
                    upload.questions_imported = len(questions_data)
                    upload.save()
                    
                    messages.success(
                        request,
                        f'Successfully imported {len(questions_data)} questions!'
                    )
                    return redirect('admin:quiz_descriptivequestionupload_changelist')
                
                except Exception as e:
                    upload.error_message = str(e)
                    upload.save()
                    messages.error(request, f'Error processing file: {str(e)}')
        else:
            form = DescriptiveQuestionUploadForm()
        
        return render(
            request,
            'admin/quiz/upload_descriptive_questions.html',
            {
                'form': form,
                'title': 'Upload Descriptive Questions',
                'opts': self.model._meta,
            }
        )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'profile') and request.user.profile.institution:
            return qs.filter(institution=request.user.profile.institution)
        return qs.none()


# ==================== AI EVALUATION LOG ADMIN ====================

@admin.register(AIEvaluationLog)
class AIEvaluationLogAdmin(admin.ModelAdmin):
    """Admin for monitoring AI evaluations"""
    list_display = [
        'answer_info', 'api_provider', 'model_used',
        'execution_time', 'success', 'created_at'
    ]
    list_filter = ['api_provider', 'success', 'created_at']
    search_fields = ['answer__attempt__user__username', 'error_message']
    readonly_fields = [
        'answer', 'api_provider', 'model_used', 'request_data',
        'response_data', 'execution_time', 'success',
        'error_message', 'created_at'
    ]
    list_per_page = 100
    
    def answer_info(self, obj):
        return f"{obj.answer.attempt.user.username} - Q{obj.answer.question.id}"
    answer_info.short_description = 'Answer'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    
    
# Admin Site Customization
admin.site.site_header = "Quiz Platform Administration"
admin.site.site_title = "Quiz Platform"
admin.site.index_title = "Dashboard"

