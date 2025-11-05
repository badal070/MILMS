from docx import Document
from .models import ActivityLog

def parse_question_from_docx(file_path):
    """
    Parse questions from Word document
    Format: Question ending with ? : or .
    4 options, correct marked with *
    """
    doc = Document(file_path)
    questions = []
    current_question = None
    options = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # Check if question
        if text.endswith(('?', ':', '.')):
            if current_question and len(options) == 4:
                questions.append({
                    'question': current_question,
                    'options': options
                })
            current_question = text
            options = []
        elif current_question:
            is_correct = text.endswith('*')
            option_text = text.rstrip('*').strip()
            if option_text:
                options.append({
                    'text': option_text,
                    'is_correct': is_correct
                })
    
    # Add last question
    if current_question and len(options) == 4:
        questions.append({
            'question': current_question,
            'options': options
        })
    
    return questions

def log_activity(user, action, description='', request=None):
    """Log user activity with IP address"""
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    ActivityLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=ip_address
    )

def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')