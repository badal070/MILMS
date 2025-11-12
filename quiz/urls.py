from django.urls import path
from . import views

app_name = 'quiz'

urlpatterns = [
    # ============ PUBLIC URLS ============
    path('', views.landing_page, name='landing'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # ============ COMMON AUTHENTICATED URLS ============
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    
    # ============ STUDENT URLS ============
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/info/', views.student_info, name='student_info'),
    path('student/quizzes/', views.student_quizzes, name='student_quizzes'),
    path('student/quiz/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    path('student/results/<int:attempt_id>/', views.quiz_results, name='quiz_results'),
    path('student/content/', views.student_content, name='student_content'),
    
    # ============ TEACHER URLS ============
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/students/', views.teacher_students, name='teacher_students'),
    path('teacher/quizzes/', views.teacher_quizzes, name='teacher_quizzes'),
    path('teacher/content/', views.teacher_content, name='teacher_content'),
    
    # ============ PRINCIPAL URLS ============
    path('principal/', views.principal_dashboard, name='principal_dashboard'),
    path('principal/teachers/', views.principal_teachers, name='principal_teachers'),
    path('principal/teacher/<int:teacher_id>/', views.principal_teacher_detail, name='principal_teacher_detail'),
    path('principal/students/', views.principal_students, name='principal_students'),
    
    # ============ CONTENT MANAGEMENT (MULTI-ROLE) ============
    path('content/<int:content_id>/view/', views.content_view, name='content_view'),
    path('content/upload/', views.content_upload, name='content_upload'),
    
    path('upload/questions/', views.upload_questions_standalone, name='upload_questions'),
    path('upload/questions/<int:upload_id>/preview/', views.preview_questions_standalone, name='preview_questions'),
    path('upload/questions/<int:upload_id>/process/', views.process_questions_standalone, name='process_questions'),
    
    # ============ STUDENT - DESCRIPTIVE QUIZ URLS ============
    path('student/descriptive-quizzes/', views.student_descriptive_quizzes, name='student_descriptive_quizzes'),
    path('student/descriptive-quiz/<int:quiz_id>/', views.take_descriptive_quiz, name='take_descriptive_quiz'),
    path('student/descriptive-results/<int:attempt_id>/', views.descriptive_quiz_results, name='descriptive_quiz_results'),
    path('student/my-descriptive-attempts/', views.my_descriptive_attempts, name='my_descriptive_attempts'),
    
    # ============ TEACHER - DESCRIPTIVE QUIZ URLS ============
    path('teacher/descriptive-quizzes/', views.teacher_descriptive_quizzes, name='teacher_descriptive_quizzes'),
    path('teacher/review-pending/', views.review_pending_attempts, name='review_pending_attempts'),
    path('teacher/review-attempt/<int:attempt_id>/', views.review_descriptive_attempt, name='review_descriptive_attempt'),
    path('teacher/descriptive-analytics/<int:quiz_id>/', views.descriptive_quiz_analytics, name='descriptive_quiz_analytics'),
    
    # ============ AJAX ENDPOINTS ============
    path('api/save-descriptive-progress/', views.save_descriptive_progress, name='save_descriptive_progress'),
]
