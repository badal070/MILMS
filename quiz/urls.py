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
]
