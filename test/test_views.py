from django.test import TestCase, Client, RequestFactory
from django.contrib.auth.models import User
from quiz.models import (
    DescriptiveQuiz, DescriptiveQuizAttempt, DescriptiveAnswer,
    UserProfile, Institution, Subject, Standard
)
from quiz.views import take_descriptive_quiz
import json

class TakeDescriptiveQuizViewTest(TestCase):
    
    def setUp(self):
        """Set up test data"""
        # Create institution
        self.institution = Institution.objects.create(name='Test School')
        
        # Create subject and standard
        self.subject = Subject.objects.create(name='Math')
        self.standard = Standard.objects.create(name='Class 10')
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create user profile
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='student',
            institution=self.institution,
            student_name='Test Student',
            roll_number='123'
        )
        
        # Create quiz
        self.quiz = DescriptiveQuiz.objects.create(
            title='Math Quiz',
            subject=self.subject,
            standard=self.standard,
            institution=self.institution,
            auto_evaluate=True,
            is_active=True
        )
    
    def test_take_descriptive_quiz_get(self):
        """Test accessing the quiz page"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(f'/student/descriptive-quiz/{self.quiz.id}/')
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'quiz/student/take_descriptive_quiz.html')
        self.assertIn('quiz', response.context)
    
    def test_take_descriptive_quiz_post_save(self):
        """Test saving progress"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            f'/student/descriptive-quiz/{self.quiz.id}/',
            {'action': 'save'},
            follow=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('Progress saved', str(response.content))
    
    def test_take_descriptive_quiz_no_profile(self):
        """Test with incomplete profile"""
        # Create user without student info
        user2 = User.objects.create_user(
            username='testuser2',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user2,
            role='student',
            institution=self.institution
        )
        
        self.client.login(username='testuser2', password='testpass123')
        response = self.client.get(
            f'/student/descriptive-quiz/{self.quiz.id}/',
            follow=True
        )
        
        self.assertRedirects(response, '/student/info/')
    
    def test_take_descriptive_quiz_access_denied(self):
        """Test access from different institution"""
        other_institution = Institution.objects.create(name='Other School')
        other_user = User.objects.create_user(
            username='otheruser',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=other_user,
            role='student',
            institution=other_institution,
            student_name='Other Student',
            roll_number='456'
        )
        
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(
            f'/student/descriptive-quiz/{self.quiz.id}/',
            follow=True
        )
        
        self.assertIn('do not have access', str(response.content))

class StudentDashboardViewTest(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        
        self.institution = Institution.objects.create(name='Test School')
        self.user = User.objects.create_user(
            username='student1',
            password='pass123'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            role='student',
            institution=self.institution,
            student_name='John Doe',
            roll_number='001'
        )
    
    def test_dashboard_displays_quizzes(self):
        """Test dashboard shows available quizzes"""
        self.client.login(username='student1', password='pass123')
        response = self.client.get('/student/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('available_quizzes', response.context)
    
    def test_dashboard_incomplete_profile_redirect(self):
        """Test redirect when profile incomplete"""
        user2 = User.objects.create_user(
            username='incomplete',
            password='pass123'
        )
        UserProfile.objects.create(
            user=user2,
            role='student',
            institution=self.institution
        )
        
        self.client.login(username='incomplete', password='pass123')
        response = self.client.get('/student/', follow=True)
        
        self.assertRedirects(response, '/student/info/')