from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from quiz.models import Institution, UserProfile, Subject, Standard, MarkingScheme, Question, Quiz

class Command(BaseCommand):
    help = 'Creates demo data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating demo data...')
        
        # Create Institution
        institution, _ = Institution.objects.get_or_create(
            code='DEMO001',
            defaults={
                'name': 'Demo School',
                'address': '123 Demo Street',
                'contact_email': 'demo@school.com',
                'is_active': True
            }
        )
        self.stdout.write(f'✓ Institution: {institution.name}')
        
        # Create Subjects
        subjects_data = ['Mathematics', 'Science', 'English', 'History']
        subjects = []
        for subject_name in subjects_data:
            subject, _ = Subject.objects.get_or_create(
                name=subject_name,
                defaults={'description': f'{subject_name} subject'}
            )
            subjects.append(subject)
        self.stdout.write(f'✓ Subjects: {len(subjects)}')
        
        # Create Standards
        standards_data = ['Class 8', 'Class 9', 'Class 10']
        standards = []
        for standard_name in standards_data:
            standard, _ = Standard.objects.get_or_create(
                name=standard_name,
                defaults={'description': f'{standard_name}'}
            )
            standards.append(standard)
        self.stdout.write(f'✓ Standards: {len(standards)}')
        
        # Create Marking Scheme
        marking, _ = MarkingScheme.objects.get_or_create(
            name='Standard (+4, -1)',
            defaults={'correct_marks': 4, 'wrong_marks': 1}
        )
        self.stdout.write(f'✓ Marking Scheme: {marking.name}')
        
        # Create Admin
        if not User.objects.filter(username='admin').exists():
            admin = User.objects.create_superuser('admin', 'admin@demo.com', 'admin123')
            UserProfile.objects.update_or_create(
                user=admin,
                defaults={'role': 'superadmin', 'institution': institution}
            )
            self.stdout.write('✓ Admin created (admin/admin123)')
        
        # Create Principal
        if not User.objects.filter(username='principal').exists():
            principal = User.objects.create_user('principal', 'principal@demo.com', 'principal123')
            UserProfile.objects.update_or_create(
                user=principal,
                defaults={'role': 'principal', 'institution': institution}
            )
            self.stdout.write('✓ Principal created (principal/principal123)')
        
        # Create Teacher
        if not User.objects.filter(username='teacher').exists():
            teacher = User.objects.create_user('teacher', 'teacher@demo.com', 'teacher123')
            UserProfile.objects.update_or_create(
                user=teacher,
                defaults={
                    'role': 'teacher',
                    'institution': institution,
                    'can_create_quiz': True,
                    'can_upload_content': True
                }
            )
            self.stdout.write('✓ Teacher created (teacher/teacher123)')
        
        # Create Students
        for i in range(1, 6):
            username = f'student{i}'
            if not User.objects.filter(username=username).exists():
                student = User.objects.create_user(username, f'student{i}@demo.com', f'student{i}123')
                UserProfile.objects.update_or_create(
                    user=student,
                    defaults={
                        'role': 'student',
                        'institution': institution,
                        'student_name': f'Student {i}',
                        'roll_number': f'STU{i:03d}'
                    }
                )
        
        self.stdout.write('✓ Students created: 5')
        
        # Create Sample Questions
        teacher = User.objects.get(username='teacher')
        sample_questions = [
            {
                'question_text': 'What is the capital of France?',
                'option_a': 'London',
                'option_b': 'Berlin',
                'option_c': 'Paris',
                'option_d': 'Madrid',
                'correct_answer': 'C'
            },
            {
                'question_text': 'What is 2 + 2?',
                'option_a': '3',
                'option_b': '4',
                'option_c': '5',
                'option_d': '6',
                'correct_answer': 'B'
            },
            {
                'question_text': 'Which planet is closest to the Sun?',
                'option_a': 'Venus',
                'option_b': 'Earth',
                'option_c': 'Mercury',
                'option_d': 'Mars',
                'correct_answer': 'C'
            },
        ]
        
        questions_created = 0
        for subject in subjects[:1]:
            for standard in standards[:1]:
                for q_data in sample_questions:
                    Question.objects.get_or_create(
                        subject=subject,
                        standard=standard,
                        institution=institution,
                        question_text=q_data['question_text'],
                        defaults={
                            'created_by': teacher,
                            'option_a': q_data['option_a'],
                            'option_b': q_data['option_b'],
                            'option_c': q_data['option_c'],
                            'option_d': q_data['option_d'],
                            'correct_answer': q_data['correct_answer']
                        }
                    )
                    questions_created += 1
        
        self.stdout.write(f'✓ Questions created: {questions_created}')
        
        # Create Sample Quiz
        quiz, created = Quiz.objects.get_or_create(
            title='Demo Quiz - Mathematics',
            defaults={
                'description': 'A sample quiz for testing',
                'subject': subjects[0],
                'standard': standards[0],
                'institution': institution,
                'marking_scheme': marking,
                'duration_minutes': 30,
                'is_active': True,
                'created_by': teacher
            }
        )
        
        if created:
            questions = Question.objects.filter(
                subject=subjects[0],
                standard=standards[0],
                institution=institution
            )
            quiz.questions.set(questions)
            self.stdout.write(f'✓ Quiz created: {quiz.title}')
        
        self.stdout.write(self.style.SUCCESS('\n=== Demo Data Created Successfully! ==='))
        self.stdout.write('\nLogin Credentials:')
        self.stdout.write('Admin: admin/admin123')
        self.stdout.write('Principal: principal/principal123')
        self.stdout.write('Teacher: teacher/teacher123')
        self.stdout.write('Students: student1/student1123 ... student5/student5123')