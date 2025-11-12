# quiz/migrations/0002_descriptive_questions.py
# Create this as a new migration file

from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('quiz', '0001_initial'),
    ]

    operations = [
        # DescriptiveQuestion Model
        migrations.CreateModel(
            name='DescriptiveQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_text', models.TextField(help_text='Enter the descriptive question')),
                ('reference_answer', models.TextField(blank=True, help_text='Model/Reference answer for evaluation')),
                ('marking_guidelines', models.TextField(blank=True, help_text='Guidelines for manual marking (key points to look for)')),
                ('max_marks', models.IntegerField(default=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)])),
                ('word_limit', models.IntegerField(default=500, help_text='Recommended word limit', validators=[django.core.validators.MinValueValidator(50)])),
                ('enable_ai_evaluation', models.BooleanField(default=True, help_text='Enable AI-powered evaluation for this question')),
                ('ai_evaluation_weightage', models.DecimalField(decimal_places=2, default=0.7, help_text='AI evaluation weight (0-1). Remainder will be manual review.', max_digits=3, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_descriptive_questions', to=settings.AUTH_USER_MODEL)),
                ('institution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_questions', to='quiz.institution')),
                ('standard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_questions', to='quiz.standard')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_questions', to='quiz.subject')),
            ],
            options={
                'verbose_name': 'Descriptive Question',
                'verbose_name_plural': 'Descriptive Questions',
                'ordering': ['-created_at'],
            },
        ),
        
        # DescriptiveQuiz Model
        migrations.CreateModel(
            name='DescriptiveQuiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=300)),
                ('description', models.TextField(blank=True)),
                ('duration_minutes', models.IntegerField(default=60, help_text='Time allowed in minutes', validators=[django.core.validators.MinValueValidator(1)])),
                ('auto_evaluate', models.BooleanField(default=True, help_text='Automatically evaluate using AI when submitted')),
                ('require_manual_review', models.BooleanField(default=True, help_text='Require teacher review after AI evaluation')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_descriptive_quizzes', to=settings.AUTH_USER_MODEL)),
                ('institution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_quizzes', to='quiz.institution')),
                ('questions', models.ManyToManyField(related_name='descriptive_quizzes', to='quiz.DescriptiveQuestion')),
                ('standard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_quizzes', to='quiz.standard')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_quizzes', to='quiz.subject')),
            ],
            options={
                'verbose_name': 'Descriptive Quiz',
                'verbose_name_plural': 'Descriptive Quizzes',
                'ordering': ['-created_at'],
            },
        ),
        
        # DescriptiveQuizAttempt Model
        migrations.CreateModel(
            name='DescriptiveQuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('ai_evaluated', 'AI Evaluated'), ('manually_reviewed', 'Manually Reviewed'), ('finalized', 'Finalized')], db_index=True, default='draft', max_length=20)),
                ('total_marks', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('ai_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=7, null=True)),
                ('manual_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=7, null=True)),
                ('final_score', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('ai_evaluated_at', models.DateTimeField(blank=True, null=True)),
                ('manually_reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('finalized_at', models.DateTimeField(blank=True, null=True)),
                ('teacher_comments', models.TextField(blank=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='quiz.descriptivequiz')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_descriptive_attempts', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descriptive_quiz_attempts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Descriptive Quiz Attempt',
                'verbose_name_plural': 'Descriptive Quiz Attempts',
                'ordering': ['-started_at'],
            },
        ),
        
        # DescriptiveAnswer Model
        migrations.CreateModel(
            name='DescriptiveAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_text', models.TextField()),
                ('word_count', models.IntegerField(default=0)),
                ('ai_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=7, null=True)),
                ('ai_evaluation_data', models.JSONField(blank=True, help_text='Complete AI evaluation response', null=True)),
                ('ai_feedback', models.TextField(blank=True)),
                ('manual_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=7, null=True)),
                ('manual_feedback', models.TextField(blank=True)),
                ('final_score', models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ('spelling_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=4, null=True)),
                ('relevance_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=4, null=True)),
                ('content_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=4, null=True)),
                ('grammar_score', models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=4, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='quiz.descriptivequizattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='quiz.descriptivequestion')),
            ],
            options={
                'ordering': ['id'],
                'unique_together': {('attempt', 'question')},
            },
        ),
        
        # DescriptiveQuestionUpload Model
        migrations.CreateModel(
            name='DescriptiveQuestionUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='descriptive_uploads/%Y/%m/', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['docx'])])),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('processed', models.BooleanField(default=False)),
                ('questions_imported', models.IntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('institution', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='quiz.institution')),
                ('standard', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='quiz.standard')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='quiz.subject')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Descriptive Question Upload',
                'verbose_name_plural': 'Descriptive Question Uploads',
                'ordering': ['-uploaded_at'],
            },
        ),
        
        # AIEvaluationLog Model
        migrations.CreateModel(
            name='AIEvaluationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_provider', models.CharField(default='huggingface', help_text='AI provider used (huggingface, openai, etc.)', max_length=50)),
                ('model_used', models.CharField(max_length=100)),
                ('request_data', models.JSONField(help_text='Request sent to API')),
                ('response_data', models.JSONField(help_text='Response from API')),
                ('execution_time', models.DecimalField(decimal_places=2, help_text='Time taken in seconds', max_digits=6)),
                ('success', models.BooleanField(default=True)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('answer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluation_logs', to='quiz.descriptiveanswer')),
            ],
            options={
                'verbose_name': 'AI Evaluation Log',
                'verbose_name_plural': 'AI Evaluation Logs',
                'ordering': ['-created_at'],
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='descriptivequestion',
            index=models.Index(fields=['subject', 'standard', 'institution'], name='quiz_descri_subject_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequestion',
            index=models.Index(fields=['is_active', 'created_at'], name='quiz_descri_is_active_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequiz',
            index=models.Index(fields=['institution', 'is_active'], name='quiz_descri_quiz_inst_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequiz',
            index=models.Index(fields=['subject', 'standard'], name='quiz_descri_quiz_subj_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequizattempt',
            index=models.Index(fields=['user', '-started_at'], name='quiz_descri_attempt_user_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequizattempt',
            index=models.Index(fields=['quiz', 'status'], name='quiz_descri_attempt_quiz_idx'),
        ),
        migrations.AddIndex(
            model_name='descriptivequizattempt',
            index=models.Index(fields=['status', '-submitted_at'], name='quiz_descri_attempt_stat_idx'),
        ),
    ]