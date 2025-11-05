from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator

from .models import (
    Quiz, QuizAttempt, Answer, Question, Subject, Standard, 
    Content, UserProfile, User, Institution
)
from .forms import ContentUploadForm
from .utils import log_activity


# ======================== AUTHENTICATION & AUTHORIZATION ========================

def landing_page(request):
    """Landing page - entry point for all users"""
    if request.user.is_authenticated:
        return redirect('quiz:dashboard')
    return render(request, 'quiz/landing.html')


def login_view(request):
    """Role-based login with strong validation"""
    if request.user.is_authenticated:
        return redirect('quiz:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        expected_role = request.POST.get('role', '')
        
        if not all([username, password, expected_role]):
            messages.error(request, 'All fields are required.')
            return render(request, 'quiz/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Ensure user has profile
            if not hasattr(user, 'profile'):
                messages.error(request, 'User profile not found. Contact administrator.')
                return render(request, 'quiz/login.html')
            
            # Verify role matches
            if user.profile.role == expected_role:
                login(request, user)
                log_activity(user, 'login', f'Logged in as {expected_role}', request)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('quiz:dashboard')
            else:
                messages.error(request, f'Invalid credentials for {expected_role} role. Please check your role selection.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'quiz/login.html')


@login_required
def logout_view(request):
    """Logout with activity logging"""
    username = request.user.username
    log_activity(request.user, 'logout', 'User logged out', request)
    logout(request)
    messages.success(request, f'Goodbye, {username}! You have been logged out successfully.')
    return redirect('quiz:landing')


@login_required
def dashboard(request):
    """Central dashboard - routes users based on role"""
    user_profile = request.user.profile
    
    # Route based on role
    role_routes = {
        'student': 'quiz:student_dashboard',
        'teacher': 'quiz:teacher_dashboard',
        'principal': 'quiz:principal_dashboard',
        'superadmin': 'admin:index'
    }
    
    redirect_url = role_routes.get(user_profile.role, 'quiz:landing')
    return redirect(redirect_url)


# ======================== ROLE CHECKERS ========================

def is_student(user):
    """Check if user is student"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'student'


def is_teacher(user):
    """Check if user is teacher"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'teacher'


def is_principal(user):
    """Check if user is principal"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'principal'


def is_staff_or_above(user):
    """Check if user is teacher, principal, or admin"""
    return user.is_authenticated and (
        user.is_staff or 
        (hasattr(user, 'profile') and user.profile.role in ['teacher', 'principal', 'superadmin'])
    )


# ======================== STUDENT VIEWS ========================

@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def student_dashboard(request):
    """Main student dashboard with all data"""
    user_profile = request.user.profile
    
    # Check if student needs to complete profile
    if not user_profile.student_name or not user_profile.roll_number:
        messages.warning(request, 'Please complete your profile information.')
        return redirect('quiz:student_info')
    
    institution = user_profile.institution
    
    # Optimized queries with prefetch and annotations
    available_quizzes = Quiz.objects.filter(
        is_active=True,
        institution=institution
    ).select_related('subject', 'standard', 'marking_scheme').prefetch_related('questions')[:6]
    
    # Student's attempts with aggregation
    attempts = QuizAttempt.objects.filter(
        user=request.user
    ).select_related('quiz__subject', 'quiz__standard')
    
    total_attempts = attempts.count()
    avg_score = attempts.aggregate(Avg('score'))['score__avg'] or 0
    best_score = attempts.aggregate(max_score=Sum('score'))['max_score'] or 0
    
    recent_attempts = attempts.order_by('-started_at')[:5]
    
    # Available content
    available_content = Content.objects.filter(
        Q(institution=institution) | Q(is_public=True)
    ).select_related('subject', 'standard', 'uploaded_by').order_by('-created_at')[:6]
    
    context = {
        'user_profile': user_profile,
        'available_quizzes': available_quizzes,
        'available_content': available_content,
        'recent_attempts': recent_attempts,
        'total_attempts': total_attempts,
        'avg_score': round(avg_score, 2),
        'best_score': round(best_score, 2),
    }
    
    return render(request, 'quiz/student/dashboard.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def student_info(request):
    """Student profile completion"""
    user_profile = request.user.profile
    
    if request.method == 'POST':
        student_name = request.POST.get('student_name', '').strip()
        roll_number = request.POST.get('roll_number', '').strip()
        
        if student_name and roll_number:
            user_profile.student_name = student_name
            user_profile.roll_number = roll_number
            user_profile.save()
            log_activity(request.user, 'user_update', 'Updated student information', request)
            messages.success(request, 'Profile updated successfully!')
            return redirect('quiz:student_dashboard')
        else:
            messages.error(request, 'Both name and roll number are required.')
    
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'quiz/student/student_info.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def student_quizzes(request):
    """List all available quizzes with filters"""
    user_profile = request.user.profile
    
    # Get filter parameters
    subject_id = request.GET.get('subject', '')
    standard_id = request.GET.get('standard', '')
    
    # Get filter options
    subjects = Subject.objects.all()
    standards = Standard.objects.all()
    
    # Build quiz query
    quizzes = Quiz.objects.filter(
        is_active=True,
        institution=user_profile.institution
    ).select_related('subject', 'standard', 'marking_scheme').prefetch_related('questions')
    
    if subject_id:
        quizzes = quizzes.filter(subject_id=subject_id)
    if standard_id:
        quizzes = quizzes.filter(standard_id=standard_id)
    
    # Pagination
    paginator = Paginator(quizzes, 9)  # 9 quizzes per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
        'subjects': subjects,
        'standards': standards,
        'selected_subject': subject_id,
        'selected_standard': standard_id,
    }
    
    return render(request, 'quiz/student/quizzes.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def take_quiz(request, quiz_id):
    """Take quiz - main assessment interface"""
    quiz = get_object_or_404(
        Quiz.objects.select_related('subject', 'standard', 'marking_scheme').prefetch_related('questions'),
        id=quiz_id,
        is_active=True
    )
    user_profile = request.user.profile
    
    # Verify access
    if quiz.institution != user_profile.institution:
        messages.error(request, 'You do not have access to this quiz.')
        return redirect('quiz:student_quizzes')
    
    # Verify student info is complete
    if not user_profile.student_name or not user_profile.roll_number:
        messages.warning(request, 'Please complete your profile first.')
        return redirect('quiz:student_info')
    
    if request.method == 'POST':
        # Create quiz attempt
        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            total_questions=quiz.questions.count()
        )
        
        correct_count = 0
        wrong_count = 0
        unanswered_count = 0
        score = 0
        
        # Bulk create answers
        answers_to_create = []
        for question in quiz.questions.all():
            selected = request.POST.get(f'question_{question.id}', '')
            is_correct = selected == question.correct_answer
            
            answers_to_create.append(Answer(
                attempt=attempt,
                question=question,
                selected_answer=selected,
                is_correct=is_correct
            ))
            
            if not selected:
                unanswered_count += 1
            elif is_correct:
                correct_count += 1
                score += float(quiz.marking_scheme.correct_marks)
            else:
                wrong_count += 1
                score -= float(quiz.marking_scheme.wrong_marks)
        
        # Bulk insert answers
        Answer.objects.bulk_create(answers_to_create)
        
        # Update attempt
        attempt.correct_answers = correct_count
        attempt.wrong_answers = wrong_count
        attempt.unanswered = unanswered_count
        attempt.score = max(0, score)  # Ensure score doesn't go negative
        attempt.completed_at = timezone.now()
        attempt.save()
        
        log_activity(request.user, 'quiz_attempt', f'Completed: {quiz.title} - Score: {attempt.score}', request)
        messages.success(request, f'Quiz submitted! You scored {attempt.score}')
        
        return redirect('quiz:quiz_results', attempt_id=attempt.id)
    
    questions = quiz.questions.all()
    
    context = {
        'user_profile': user_profile,
        'quiz': quiz,
        'questions': questions,
    }
    
    return render(request, 'quiz/student/take_quiz.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def quiz_results(request, attempt_id):
    """View quiz results"""
    attempt = get_object_or_404(
        QuizAttempt.objects.select_related('quiz__subject', 'quiz__standard', 'quiz__marking_scheme'),
        id=attempt_id,
        user=request.user
    )
    
    answers = attempt.answers.select_related('question').all()
    
    context = {
        'user_profile': request.user.profile,
        'attempt': attempt,
        'answers': answers,
    }
    
    return render(request, 'quiz/student/results.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def student_content(request):
    """View available learning content"""
    user_profile = request.user.profile
    
    # Get filter parameters
    subject_id = request.GET.get('subject', '')
    standard_id = request.GET.get('standard', '')
    
    subjects = Subject.objects.all()
    standards = Standard.objects.all()
    
    # Build content query
    contents = Content.objects.filter(
        Q(institution=user_profile.institution) | Q(is_public=True)
    ).select_related('subject', 'standard', 'uploaded_by')
    
    if subject_id:
        contents = contents.filter(subject_id=subject_id)
    if standard_id:
        contents = contents.filter(standard_id=standard_id)
    
    contents = contents.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(contents, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
        'subjects': subjects,
        'standards': standards,
        'selected_subject': subject_id,
        'selected_standard': standard_id,
    }
    
    return render(request, 'quiz/student/content.html', context)


# ======================== TEACHER VIEWS ========================

@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def teacher_dashboard(request):
    """Teacher main dashboard"""
    user_profile = request.user.profile
    institution = user_profile.institution
    
    # Get teacher's quizzes with annotations
    teacher_quizzes = Quiz.objects.filter(
        created_by=request.user,
        institution=institution
    ).annotate(
        total_attempts=Count('attempts')
    )
    
    # Get statistics
    stats = {
        'quizzes_created': teacher_quizzes.count(),
        'contents_uploaded': Content.objects.filter(uploaded_by=request.user, institution=institution).count(),
        'total_students': UserProfile.objects.filter(institution=institution, role='student').count(),
        'total_attempts': QuizAttempt.objects.filter(quiz__in=teacher_quizzes).count(),
        'can_create_quiz': user_profile.can_create_quiz,
        'can_upload_content': user_profile.can_upload_content,
    }
    
    # Recent quiz attempts on teacher's quizzes
    recent_attempts = QuizAttempt.objects.filter(
        quiz__in=teacher_quizzes
    ).select_related('user__profile', 'quiz').order_by('-started_at')[:10]
    
    context = {
        'user_profile': user_profile,
        **stats,
        'recent_attempts': recent_attempts,
    }
    
    return render(request, 'quiz/teacher/dashboard.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def teacher_students(request):
    """View all students with performance"""
    user_profile = request.user.profile
    institution = user_profile.institution
    
    # Get students with aggregated data
    students = User.objects.filter(
        profile__institution=institution,
        profile__role='student'
    ).select_related('profile').annotate(
        total_attempts=Count('quiz_attempts'),
        avg_score=Avg('quiz_attempts__score'),
        total_score=Sum('quiz_attempts__score')
    ).order_by('profile__student_name')
    
    # Get recent attempts for each student
    student_data = []
    for student in students:
        recent = QuizAttempt.objects.filter(
            user=student
        ).select_related('quiz').order_by('-started_at')[:3]
        
        student_data.append({
            'user': student,
            'profile': student.profile,
            'total_attempts': student.total_attempts or 0,
            'avg_score': round(student.avg_score or 0, 2),
            'recent_attempts': recent,
        })
    
    context = {
        'user_profile': user_profile,
        'student_data': student_data,
    }
    
    return render(request, 'quiz/teacher/students.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def teacher_quizzes(request):
    """Manage teacher's quizzes"""
    user_profile = request.user.profile
    
    quizzes = Quiz.objects.filter(
        created_by=request.user,
        institution=user_profile.institution
    ).select_related('subject', 'standard', 'marking_scheme').annotate(
        total_attempts=Count('attempts'),
        avg_score=Avg('attempts__score')
    ).order_by('-created_at')
    
    context = {
        'user_profile': user_profile,
        'quizzes': quizzes,
    }
    
    return render(request, 'quiz/teacher/quizzes.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def teacher_content(request):
    """Manage teacher's uploaded content"""
    user_profile = request.user.profile
    
    contents = Content.objects.filter(
        uploaded_by=request.user,
        institution=user_profile.institution
    ).select_related('subject', 'standard').order_by('-created_at')
    
    context = {
        'user_profile': user_profile,
        'contents': contents,
    }
    
    return render(request, 'quiz/teacher/content.html', context)


# ======================== PRINCIPAL VIEWS ========================

@login_required
@user_passes_test(is_principal, login_url='quiz:dashboard')
def principal_dashboard(request):
    """Principal main dashboard"""
    user_profile = request.user.profile
    institution = user_profile.institution
    
    # Get comprehensive statistics
    stats = {
        'total_students': UserProfile.objects.filter(institution=institution, role='student').count(),
        'total_teachers': UserProfile.objects.filter(institution=institution, role='teacher').count(),
        'total_quizzes': Quiz.objects.filter(institution=institution).count(),
        'active_quizzes': Quiz.objects.filter(institution=institution, is_active=True).count(),
        'total_attempts': QuizAttempt.objects.filter(quiz__institution=institution).count(),
        'total_content': Content.objects.filter(institution=institution).count(),
    }
    
    # Average performance
    avg_performance = QuizAttempt.objects.filter(
        quiz__institution=institution
    ).aggregate(
        avg_score=Avg('score'),
        avg_correct=Avg('correct_answers')
    )
    
    stats.update({
        'avg_score': round(avg_performance['avg_score'] or 0, 2),
        'avg_correct': round(avg_performance['avg_correct'] or 0, 2),
    })
    
    # Recent activities
    recent_attempts = QuizAttempt.objects.filter(
        quiz__institution=institution
    ).select_related('user__profile', 'quiz').order_by('-started_at')[:10]
    
    context = {
        'user_profile': user_profile,
        **stats,
        'recent_attempts': recent_attempts,
    }
    
    return render(request, 'quiz/principal/dashboard.html', context)


@login_required
@user_passes_test(is_principal, login_url='quiz:dashboard')
def principal_teachers(request):
    """View all teachers"""
    user_profile = request.user.profile
    institution = user_profile.institution
    
    teachers = User.objects.filter(
        profile__institution=institution,
        profile__role='teacher'
    ).select_related('profile').annotate(
        quizzes_count=Count('created_quizzes', filter=Q(created_quizzes__institution=institution)),
        contents_count=Count('uploaded_content', filter=Q(uploaded_content__institution=institution))
    ).order_by('username')
    
    teacher_data = []
    for teacher in teachers:
        teacher_data.append({
            'user': teacher,
            'profile': teacher.profile,
            'quizzes_created': teacher.quizzes_count,
            'contents_uploaded': teacher.contents_count,
        })
    
    context = {
        'user_profile': user_profile,
        'teacher_data': teacher_data,
    }
    
    return render(request, 'quiz/principal/teachers.html', context)


@login_required
@user_passes_test(is_principal, login_url='quiz:dashboard')
def principal_teacher_detail(request, teacher_id):
    """View specific teacher details"""
    user_profile = request.user.profile
    
    teacher = get_object_or_404(
        User,
        id=teacher_id,
        profile__role='teacher',
        profile__institution=user_profile.institution
    )
    
    quizzes = Quiz.objects.filter(
        created_by=teacher,
        institution=user_profile.institution
    ).select_related('subject', 'standard').annotate(
        total_attempts=Count('attempts')
    )
    
    contents = Content.objects.filter(
        uploaded_by=teacher,
        institution=user_profile.institution
    ).select_related('subject', 'standard')
    
    context = {
        'user_profile': user_profile,
        'teacher': teacher,
        'quizzes': quizzes,
        'contents': contents,
    }
    
    return render(request, 'quiz/principal/teacher_detail.html', context)


@login_required
@user_passes_test(is_principal, login_url='quiz:dashboard')
def principal_students(request):
    """View all students with filters"""
    user_profile = request.user.profile
    institution = user_profile.institution
    
    standard_id = request.GET.get('standard', '')
    standards = Standard.objects.all()
    
    students = User.objects.filter(
        profile__institution=institution,
        profile__role='student'
    ).select_related('profile').annotate(
        total_attempts=Count('quiz_attempts'),
        avg_score=Avg('quiz_attempts__score')
    ).order_by('profile__student_name')
    
    student_data = []
    for student in students:
        # Get standards from student's quiz attempts
        student_standards = QuizAttempt.objects.filter(
            user=student
        ).values_list('quiz__standard__name', flat=True).distinct()
        
        standards_str = ', '.join(student_standards) if student_standards else 'N/A'
        
        # Apply standard filter
        if standard_id and standard_id not in standards_str:
            continue
        
        student_data.append({
            'user': student,
            'profile': student.profile,
            'total_attempts': student.total_attempts or 0,
            'avg_score': round(student.avg_score or 0, 2),
            'standards': standards_str,
        })
    
    context = {
        'user_profile': user_profile,
        'student_data': student_data,
        'standards': standards,
        'selected_standard': standard_id,
    }
    
    return render(request, 'quiz/principal/students.html', context)


# ======================== CONTENT MANAGEMENT ========================

@login_required
def content_view(request, content_id):
    """View PDF content"""
    content = get_object_or_404(Content, id=content_id)
    user_profile = request.user.profile
    
    # Check access permission
    if not content.is_public:
        if not user_profile.institution or content.institution != user_profile.institution:
            messages.error(request, 'You do not have permission to access this content.')
            return redirect('quiz:student_content' if user_profile.role == 'student' else 'quiz:teacher_content')
    
    # Increment view count
    Content.objects.filter(id=content_id).update(view_count=models.F('view_count') + 1)
    
    log_activity(request.user, 'content_view', f'Viewed: {content.title}', request)
    
    try:
        return FileResponse(content.file.open('rb'), content_type='application/pdf')
    except Exception as e:
        messages.error(request, 'Error loading PDF file.')
        raise Http404("File not found")


@login_required
@user_passes_test(is_staff_or_above, login_url='quiz:dashboard')
def content_upload(request):
    """Upload new content (teachers and principals)"""
    user_profile = request.user.profile
    
    # Check permission
    if user_profile.role == 'teacher' and not user_profile.can_upload_content:
        messages.error(request, 'You do not have permission to upload content.')
        return redirect('quiz:teacher_dashboard')
    
    if request.method == 'POST':
        form = ContentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.save(commit=False)
            content.uploaded_by = request.user
            content.institution = user_profile.institution
            content.content_type = 'pdf'
            content.save()
            
            log_activity(request.user, 'content_upload', f'Uploaded: {content.title}', request)
            messages.success(request, f'Content "{content.title}" uploaded successfully!')
            
            return redirect('quiz:teacher_content' if user_profile.role == 'teacher' else 'quiz:principal_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ContentUploadForm()
    
    context = {
        'user_profile': user_profile,
        'form': form,
    }
    
    return render(request, 'quiz/common/content_upload.html', context)


# ======================== HELPER/UTILITY VIEWS ========================

@login_required
def profile_view(request):
    """View user profile"""
    user_profile = request.user.profile
    
    # Get user-specific stats
    if user_profile.role == 'student':
        stats = {
            'total_attempts': QuizAttempt.objects.filter(user=request.user).count(),
            'avg_score': QuizAttempt.objects.filter(user=request.user).aggregate(Avg('score'))['score__avg'] or 0,
        }
    elif user_profile.role == 'teacher':
        stats = {
            'quizzes_created': Quiz.objects.filter(created_by=request.user).count(),
            'contents_uploaded': Content.objects.filter(uploaded_by=request.user).count(),
        }
    else:
        stats = {}
    
    context = {
        'user_profile': user_profile,
        'stats': stats,
    }
    
    return render(request, 'quiz/common/profile.html', context)


# Import for view_count update
from django.db import models
