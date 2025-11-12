from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from .forms import QuestionUploadForm
from .utils import parse_question_from_docx
from .models import QuestionUpload
from django.db import transaction
from .models import (
    Quiz, QuizAttempt, Answer, Question, Subject, Standard, 
    Content, UserProfile, User, Institution, DescriptiveQuiz, DescriptiveQuizAttempt, DescriptiveAnswer
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

@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def student_descriptive_quizzes(request):
    """List all available descriptive quizzes"""
    user_profile = request.user.profile
    
    # Get filter parameters
    subject_id = request.GET.get('subject', '')
    standard_id = request.GET.get('standard', '')
    
    subjects = Subject.objects.all()
    standards = Standard.objects.all()
    
    # Build quiz query
    quizzes = DescriptiveQuiz.objects.filter(
        is_active=True,
        institution=user_profile.institution
    ).select_related('subject', 'standard').prefetch_related('questions')
    
    if subject_id:
        quizzes = quizzes.filter(subject_id=subject_id)
    if standard_id:
        quizzes = quizzes.filter(standard_id=standard_id)
    
    # Pagination
    paginator = Paginator(quizzes, 9)
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
    
    return render(request, 'quiz/student/descriptive_quizzes.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def take_descriptive_quiz(request, quiz_id):
    """Take descriptive quiz"""
    quiz = get_object_or_404(
        DescriptiveQuiz.objects.select_related('subject', 'standard').prefetch_related('questions'),
        id=quiz_id,
        is_active=True
    )
    user_profile = request.user.profile
    
    # Verify access
    if quiz.institution != user_profile.institution:
        messages.error(request, 'You do not have access to this quiz.')
        return redirect('quiz:student_descriptive_quizzes')
    
    # Verify student info
    if not user_profile.student_name or not user_profile.roll_number:
        messages.warning(request, 'Please complete your profile first.')
        return redirect('quiz:student_info')
    
    # Check for existing draft
    existing_attempt = DescriptiveQuizAttempt.objects.filter(
        user=request.user,
        quiz=quiz,
        status='draft'
    ).first()
    
    if existing_attempt:
        attempt = existing_attempt
    else:
        # Create new attempt
        attempt = DescriptiveQuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            total_marks=quiz.total_marks
        )
        
        # Create answer placeholders
        for question in quiz.questions.all():
            DescriptiveAnswer.objects.create(
                attempt=attempt,
                question=question,
                answer_text=''
            )
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        
        # Save all answers
        for question in quiz.questions.all():
            answer_key = f'answer_{question.id}'
            answer_text = request.POST.get(answer_key, '').strip()
            
            answer, created = DescriptiveAnswer.objects.get_or_create(
                attempt=attempt,
                question=question,
                defaults={'answer_text': answer_text}
            )
            
            if not created:
                answer.answer_text = answer_text
                answer.calculate_word_count()
                answer.save()
        
        if action == 'submit':
            # Submit the attempt
            attempt.status = 'submitted'
            attempt.submitted_at = timezone.now()
            attempt.save()
            
            # Trigger AI evaluation if enabled
            if quiz.auto_evaluate:
                try:
                    api_key = os.getenv('HUGGINGFACE_API_KEY')
                    if api_key:
                        for answer in attempt.answers.all():
                            if answer.answer_text and answer.question.enable_ai_evaluation:
                                result = evaluate_descriptive_answer(
                                    api_key=api_key,
                                    question=answer.question.question_text,
                                    user_answer=answer.answer_text,
                                    standard_answer=answer.question.reference_answer,
                                    max_score=answer.question.max_marks
                                )
                                
                                answer.ai_score = result['overall_score']
                                answer.ai_evaluation_data = result
                                answer.ai_feedback = result['feedback']
                                answer.spelling_score = result['spelling_analysis'].get('spelling_score', 0)
                                answer.relevance_score = result['relevance_analysis'].get('relevance_score', 0)
                                answer.content_score = result['content_analysis'].get('content_score', 0)
                                answer.grammar_score = result['grammar_analysis'].get('grammar_score', 0)
                                answer.final_score = answer.ai_score
                                answer.save()
                        
                        attempt.ai_score = sum(a.ai_score or 0 for a in attempt.answers.all())
                        attempt.final_score = attempt.ai_score
                        attempt.status = 'ai_evaluated'
                        attempt.ai_evaluated_at = timezone.now()
                        attempt.save()
                        
                        messages.success(request, 'Quiz submitted and AI evaluation completed!')
                    else:
                        messages.success(request, 'Quiz submitted! Awaiting teacher review.')
                except Exception as e:
                    messages.warning(request, f'Quiz submitted! AI evaluation will be done later. ({str(e)})')
            else:
                messages.success(request, 'Quiz submitted! Awaiting teacher review.')
            
            log_activity(request.user, 'quiz_attempt', f'Completed descriptive: {quiz.title}', request)
            return redirect('quiz:descriptive_quiz_results', attempt_id=attempt.id)
        
        else:
            # Just save as draft
            messages.success(request, 'Progress saved! You can continue later.')
    
    questions = quiz.questions.all()
    answers = {a.question_id: a for a in attempt.answers.all()}
    
    context = {
        'user_profile': user_profile,
        'quiz': quiz,
        'attempt': attempt,
        'questions': questions,
        'answers': answers,
    }
    
    return render(request, 'quiz/student/take_descriptive_quiz.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def descriptive_quiz_results(request, attempt_id):
    """View descriptive quiz results"""
    attempt = get_object_or_404(
        DescriptiveQuizAttempt.objects.select_related(
            'quiz__subject', 'quiz__standard'
        ),
        id=attempt_id,
        user=request.user
    )
    
    if attempt.status == 'draft':
        messages.warning(request, 'This attempt has not been submitted yet.')
        return redirect('quiz:take_descriptive_quiz', quiz_id=attempt.quiz.id)
    
    answers = attempt.answers.select_related('question').all()
    
    context = {
        'user_profile': request.user.profile,
        'attempt': attempt,
        'answers': answers,
    }
    
    return render(request, 'quiz/student/descriptive_results.html', context)


@login_required
@user_passes_test(is_student, login_url='quiz:dashboard')
def my_descriptive_attempts(request):
    """View all descriptive quiz attempts"""
    user_profile = request.user.profile
    
    attempts = DescriptiveQuizAttempt.objects.filter(
        user=request.user
    ).exclude(
        status='draft'
    ).select_related('quiz__subject', 'quiz__standard').order_by('-submitted_at')
    
    # Pagination
    paginator = Paginator(attempts, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
    }
    
    return render(request, 'quiz/student/my_descriptive_attempts.html', context)

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


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def teacher_descriptive_quizzes(request):
    """View teacher's descriptive quizzes"""
    user_profile = request.user.profile
    
    quizzes = DescriptiveQuiz.objects.filter(
        created_by=request.user,
        institution=user_profile.institution
    ).select_related('subject', 'standard').annotate(
        total_attempts=Count('attempts')
    ).order_by('-created_at')
    
    context = {
        'user_profile': user_profile,
        'quizzes': quizzes,
    }
    
    return render(request, 'quiz/teacher/descriptive_quizzes.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def review_pending_attempts(request):
    """View attempts pending review"""
    user_profile = request.user.profile
    
    # Get attempts needing review (submitted or ai_evaluated)
    attempts = DescriptiveQuizAttempt.objects.filter(
        quiz__institution=user_profile.institution,
        quiz__created_by=request.user,
        status__in=['submitted', 'ai_evaluated']
    ).select_related(
        'user__profile', 'quiz'
    ).order_by('-submitted_at')
    
    # Pagination
    paginator = Paginator(attempts, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user_profile': user_profile,
        'page_obj': page_obj,
    }
    
    return render(request, 'quiz/teacher/review_pending_attempts.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def review_descriptive_attempt(request, attempt_id):
    """Review individual descriptive attempt"""
    attempt = get_object_or_404(
        DescriptiveQuizAttempt.objects.select_related('quiz', 'user__profile'),
        id=attempt_id
    )
    
    user_profile = request.user.profile
    
    # Verify teacher has access
    if attempt.quiz.created_by != request.user:
        messages.error(request, 'You do not have permission to review this attempt.')
        return redirect('quiz:teacher_dashboard')
    
    answers = attempt.answers.select_related('question').all()
    
    if request.method == 'POST':
        # Process manual scores
        for answer in answers:
            score_key = f'score_{answer.id}'
            feedback_key = f'feedback_{answer.id}'
            
            if score_key in request.POST:
                try:
                    manual_score = float(request.POST[score_key])
                    
                    # Validate score
                    if manual_score < 0 or manual_score > answer.question.max_marks:
                        messages.error(
                            request,
                            f'Invalid score for question {answer.question.id}. Must be between 0 and {answer.question.max_marks}'
                        )
                        continue
                    
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
                    messages.error(request, f'Invalid score value for question {answer.question.id}')
        
        # Update attempt
        attempt.manual_score = sum(a.manual_score or 0 for a in answers)
        attempt.final_score = sum(a.final_score for a in answers)
        attempt.status = 'manually_reviewed'
        attempt.reviewed_by = request.user
        attempt.manually_reviewed_at = timezone.now()
        attempt.teacher_comments = request.POST.get('teacher_comments', '')
        attempt.save()
        
        log_activity(
            request.user,
            'quiz_attempt',
            f'Reviewed descriptive attempt: {attempt.user.username} - {attempt.quiz.title}',
            request
        )
        
        messages.success(request, f'Review saved for {attempt.user.profile.display_name}!')
        return redirect('quiz:review_pending_attempts')
    
    context = {
        'user_profile': user_profile,
        'attempt': attempt,
        'answers': answers,
    }
    
    return render(request, 'quiz/teacher/review_descriptive_attempt.html', context)


@login_required
@user_passes_test(is_teacher, login_url='quiz:dashboard')
def descriptive_quiz_analytics(request, quiz_id):
    """View analytics for a specific descriptive quiz"""
    quiz = get_object_or_404(
        DescriptiveQuiz,
        id=quiz_id,
        created_by=request.user
    )
    
    attempts = DescriptiveQuizAttempt.objects.filter(
        quiz=quiz
    ).exclude(status='draft').select_related('user__profile')
    
    # Calculate statistics
    stats = {
        'total_attempts': attempts.count(),
        'submitted': attempts.filter(status='submitted').count(),
        'ai_evaluated': attempts.filter(status='ai_evaluated').count(),
        'manually_reviewed': attempts.filter(status='manually_reviewed').count(),
        'finalized': attempts.filter(status='finalized').count(),
        'avg_score': attempts.aggregate(Avg('final_score'))['final_score__avg'] or 0,
    }
    
    # Question-wise analysis
    question_stats = []
    for question in quiz.questions.all():
        answers = DescriptiveAnswer.objects.filter(
            attempt__quiz=quiz,
            question=question
        ).exclude(attempt__status='draft')
        
        question_stats.append({
            'question': question,
            'total_answers': answers.count(),
            'avg_ai_score': answers.aggregate(Avg('ai_score'))['ai_score__avg'] or 0,
            'avg_manual_score': answers.aggregate(Avg('manual_score'))['manual_score__avg'] or 0,
            'avg_final_score': answers.aggregate(Avg('final_score'))['final_score__avg'] or 0,
        })
    
    context = {
        'user_profile': request.user.profile,
        'quiz': quiz,
        'stats': stats,
        'question_stats': question_stats,
        'attempts': attempts[:10],  # Recent 10
    }
    
    return render(request, 'quiz/teacher/descriptive_quiz_analytics.html', context)

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


# Import for view_count update
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

@login_required
@user_passes_test(is_staff_or_above, login_url='quiz:dashboard')
def upload_questions_standalone(request):
    """Standalone question upload view (accessible outside admin)"""
    user_profile = request.user.profile
    
    # Check permission
    if user_profile.role == 'teacher' and not user_profile.can_create_quiz:
        messages.error(request, 'You do not have permission to upload questions.')
        return redirect('quiz:teacher_dashboard')
    
    if request.method == 'POST':
        form = QuestionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                upload = form.save(commit=False)
                upload.uploaded_by = request.user
                upload.institution = user_profile.institution
                upload.save()
                
                log_activity(request.user, 'content_upload', 
                           f'Uploaded question file: {upload.file.name}', request)
                
                messages.success(request, 'File uploaded! Redirecting to preview...')
                return redirect('quiz:preview_questions', upload_id=upload.id)
            except Exception as e:
                messages.error(request, f'Upload failed: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = QuestionUploadForm()
    
    context = {
        'user_profile': user_profile,
        'form': form,
    }
    return render(request, 'quiz/common/upload_questions.html', context)


@login_required
@user_passes_test(is_staff_or_above, login_url='quiz:dashboard')
def preview_questions_standalone(request, upload_id):
    """Preview questions before importing (standalone)"""
    from .utils import parse_question_from_docx, parse_question_from_pdf, validate_questions, preview_parsed_questions
    
    user_profile = request.user.profile
    upload = get_object_or_404(QuestionUpload, id=upload_id)
    
    # Verify access
    if not request.user.is_superuser:
        if upload.institution != user_profile.institution:
            messages.error(request, 'Access denied.')
            return redirect('quiz:teacher_dashboard')
    
    if upload.processed:
        messages.info(request, 'This file has already been processed.')
        return redirect('quiz:teacher_dashboard')
    
    try:
        file_ext = upload.file.name.split('.')[-1].lower()
        
        if file_ext == 'docx':
            questions = parse_question_from_docx(upload.file.path)
        elif file_ext == 'pdf':
            questions = parse_question_from_pdf(upload.file.path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        is_valid, errors = validate_questions(questions)
        preview_text = preview_parsed_questions(questions, max_questions=5)
        
        context = {
            'user_profile': user_profile,
            'upload': upload,
            'questions': questions,
            'question_count': len(questions),
            'is_valid': is_valid,
            'errors': errors,
            'preview_text': preview_text,
        }
        
        return render(request, 'quiz/common/preview_questions.html', context)
        
    except Exception as e:
        upload.error_message = str(e)
        upload.processed = True
        upload.save()
        messages.error(request, f'Error parsing file: {str(e)}')
        return redirect('quiz:teacher_dashboard')


@login_required
@transaction.atomic
@user_passes_test(is_staff_or_above, login_url='quiz:dashboard')
def process_questions_standalone(request, upload_id):
    """Process and import questions (standalone)"""
    from .utils import parse_question_from_docx, parse_question_from_pdf
    
    user_profile = request.user.profile
    upload = get_object_or_404(QuestionUpload, id=upload_id)
    
    # Verify access
    if not request.user.is_superuser:
        if upload.institution != user_profile.institution:
            messages.error(request, 'Access denied.')
            return redirect('quiz:teacher_dashboard')
    
    if upload.processed:
        messages.warning(request, 'This file has already been processed.')
        return redirect('quiz:teacher_dashboard')
    
    try:
        file_ext = upload.file.name.split('.')[-1].lower()
        
        if file_ext == 'docx':
            questions_data = parse_question_from_docx(upload.file.path)
        elif file_ext == 'pdf':
            questions_data = parse_question_from_pdf(upload.file.path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        imported_count = 0
        skipped_count = 0
        
        for q_data in questions_data:
            try:
                correct_option = None
                options_dict = {'A': '', 'B': '', 'C': '', 'D': ''}
                
                for idx, opt in enumerate(q_data['options'][:4]):
                    option_letter = chr(65 + idx)
                    options_dict[option_letter] = opt['text'][:500]
                    if opt['is_correct']:
                        correct_option = option_letter
                
                if correct_option and q_data['question']:
                    Question.objects.create(
                        subject=upload.subject,
                        standard=upload.standard,
                        institution=upload.institution,
                        created_by=request.user,
                        question_text=q_data['question'][:1000],
                        option_a=options_dict['A'],
                        option_b=options_dict['B'],
                        option_c=options_dict['C'],
                        option_d=options_dict['D'],
                        correct_answer=correct_option
                    )
                    imported_count += 1
                else:
                    skipped_count += 1
            except Exception:
                skipped_count += 1
        
        upload.processed = True
        upload.questions_imported = imported_count
        if skipped_count > 0:
            upload.error_message = f"Skipped {skipped_count} questions due to errors"
        upload.save()
        
        log_activity(request.user, 'quiz_create',
                   f'Imported {imported_count} questions from {upload.file.name}', request)
        
        if imported_count > 0:
            messages.success(request, f'Successfully imported {imported_count} questions!')
        else:
            messages.error(request, 'No questions were imported.')
        
        return redirect('quiz:teacher_dashboard')
        
    except Exception as e:
        upload.processed = True
        upload.error_message = str(e)
        upload.save()
        messages.error(request, f'Import failed: {str(e)}')
        return redirect('quiz:teacher_dashboard')
# Import for view_count update
from django.db import models



from .descriptive_evaluation import evaluate_descriptive_answer
from .utils import log_activity

@login_required
def save_descriptive_progress(request):
    """AJAX endpoint to save progress without submitting"""
    if request.method == 'POST':
        attempt_id = request.POST.get('attempt_id')
        question_id = request.POST.get('question_id')
        answer_text = request.POST.get('answer_text', '')
        
        try:
            attempt = DescriptiveQuizAttempt.objects.get(
                id=attempt_id,
                user=request.user,
                status='draft'
            )
            
            answer = DescriptiveAnswer.objects.get(
                attempt=attempt,
                question_id=question_id
            )
            
            answer.answer_text = answer_text
            answer.calculate_word_count()
            answer.save()
            
            return JsonResponse({
                'success': True,
                'word_count': answer.word_count,
                'message': 'Progress saved'
            })
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False}, status=400)