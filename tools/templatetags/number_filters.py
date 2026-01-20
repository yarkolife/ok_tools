"""Template filters for number formatting."""

from django import template

register = template.Library()


@register.filter(name='decimal_point')
def decimal_point(value, decimals=1):
    """
    Format a number with a decimal point (dot) regardless of locale.
    
    This is useful for HTML5 number inputs which require dot as decimal separator.
    
    Args:
        value: Number to format
        decimals: Number of decimal places (default: 1)
        
    Returns:
        Formatted string with dot as decimal separator
    """
    if value is None:
        return ''
    
    try:
        # Format number with specified decimal places
        formatted = f"{float(value):.{decimals}f}"
        return formatted
    except (ValueError, TypeError):
        return str(value) if value else ''
