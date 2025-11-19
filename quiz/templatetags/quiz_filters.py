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

@register.filter
def get_item(dictionary, key):
    """
    Get item from dictionary by key
    Usage: {{ mydict|get_item:key }}
    """
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def get_attr(obj, attr):
    """
    Get attribute from object
    Usage: {{ myobject|get_attr:"attribute_name" }}
    """
    if obj is None:
        return ''
    try:
        return getattr(obj, attr, '')
    except (AttributeError, TypeError):
        return ''

@register.filter
def mul(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0