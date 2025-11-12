from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('quiz', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='questionupload',
            name='file',
            field=models.FileField(
                upload_to='question_uploads/%Y/%m/',
                validators=[django.core.validators.FileExtensionValidator(
                    allowed_extensions=['docx', 'pdf']
                )]
            ),
        ),
    ]