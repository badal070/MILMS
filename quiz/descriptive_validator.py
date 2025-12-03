"""
Descriptive Answer Validator
Pre-submission validation to ensure quality answers
"""

import re
from typing import Dict, List
from .models import DescriptiveQuestion


def validate_descriptive_answer(answer_text: str, question: DescriptiveQuestion) -> Dict:
    """
    Validate a descriptive answer before submission
    
    Returns:
        {
            'is_valid': bool,
            'should_evaluate': bool,
            'errors': List[str],
            'warnings': List[str]
        }
    """
    errors = []
    warnings = []
    
    # Clean answer
    answer_text = answer_text.strip()
    
    # 1. Check if answer is empty
    if not answer_text:
        errors.append("Answer cannot be empty")
        return {
            'is_valid': False,
            'should_evaluate': False,
            'errors': errors,
            'warnings': warnings
        }
    
    # 2. Check minimum length (at least 20 words)
    word_count = len(answer_text.split())
    if word_count < 20:
        errors.append(f"Answer too short ({word_count} words). Minimum 20 words required.")
    
    # 3. Check if answer is mostly gibberish
    # Count ratio of actual words to total characters
    avg_word_length = len(answer_text.replace(' ', '')) / max(word_count, 1)
    if avg_word_length < 3:  # Average word length too short
        warnings.append("Answer may contain excessive gibberish or incomplete words")
    
    # 4. Check for excessive repetition
    words = answer_text.lower().split()
    unique_words = set(words)
    repetition_ratio = len(words) / max(len(unique_words), 1)
    if repetition_ratio > 3.0:
        warnings.append("Answer contains excessive word repetition")
    
    # 5. Check for copy-paste indicators (very long lines without breaks)
    lines = answer_text.split('\n')
    max_line_length = max(len(line) for line in lines) if lines else 0
    if max_line_length > 500:
        warnings.append("Answer may be copy-pasted content without proper formatting")
    
    # 6. Check word limit
    if question.word_limit:
        if word_count > question.word_limit * 1.5:
            warnings.append(
                f"Answer significantly exceeds recommended limit "
                f"({word_count} vs {question.word_limit} words)"
            )
    
    # 7. Check for minimum sentence count
    sentences = re.split(r'[.!?]+', answer_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) < 2:
        warnings.append("Answer should contain at least 2 complete sentences")
    
    # Determine validation result
    is_valid = len(errors) == 0
    should_evaluate = is_valid and word_count >= 20
    
    return {
        'is_valid': is_valid,
        'should_evaluate': should_evaluate,
        'errors': errors,
        'warnings': warnings
    }


def validate_bulk_answers(answers_data: List[tuple]) -> Dict:
    """
    Validate multiple answers at once
    
    Args:
        answers_data: List of (answer_text, question) tuples
    
    Returns:
        {
            'all_valid': bool,
            'results': List[Dict],
            'total_errors': int,
            'total_warnings': int
        }
    """
    results = []
    total_errors = 0
    total_warnings = 0
    
    for answer_text, question in answers_data:
        result = validate_descriptive_answer(answer_text, question)
        results.append(result)
        total_errors += len(result['errors'])
        total_warnings += len(result['warnings'])
    
    return {
        'all_valid': total_errors == 0,
        'results': results,
        'total_errors': total_errors,
        'total_warnings': total_warnings
    }