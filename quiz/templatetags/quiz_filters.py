from django import template

register = template.Library()

@register.filter
def chr_filter(value):
    """Convert integer to character (A=65, B=66, etc.)"""
    try:
        return chr(int(value))
    except (ValueError, TypeError):
        return ''

@register.filter
def option_letter(index):
    """Convert 1-based index to option letter (1=A, 2=B, etc.)"""
    letters = ['A', 'B', 'C', 'D']
    try:
        return letters[int(index) - 1]
    except (ValueError, TypeError, IndexError):
        return ''