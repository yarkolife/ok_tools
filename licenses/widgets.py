from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


class TagsInputWidget(forms.TextInput):
    """
    Custom widget for tags input with comma separation.
    
    Provides a user-friendly interface for entering tags with clear
    instructions and automatic comma separation.
    """
    
    template_name = 'licenses/widgets/tags_input.html'
    
    def __init__(self, attrs=None):
        default_attrs = {
            'placeholder': _('Enter tags separated by commas (e.g., tag1, tag2, tag3)'),
            'class': 'tags-input',
            'maxlength': 500,  # Reasonable limit for tags
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)
    
    def format_value(self, value):
        """
        Convert list of tags to comma-separated string for display.
        
        Args:
            value: List of tags or None
            
        Returns:
            Comma-separated string of tags
        """
        # Handle None, empty list, or falsy values
        if value is None or value == [] or value == '' or value is False:
            return ''
        
        # Handle list of tags (JSONField returns list directly)
        if isinstance(value, list):
            return ', '.join(str(tag).strip() for tag in value if tag)
        
        # Handle string representation
        if isinstance(value, str):
            # If it's the string "null" or "None", return empty
            if value.lower() in ('null', 'none'):
                return ''
            
            # If it looks like JSON array, parse it
            # Only parse if value is definitely a string (not a list)
            import json
            try:
                # Ensure value is a string before attempting JSON parsing
                if (value.startswith('[') and value.endswith(']')):
                    # Only parse if we're sure it's a string representation
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return ', '.join(str(tag).strip() for tag in parsed if tag)
            except (json.JSONDecodeError, ValueError, TypeError):
                # If parsing fails, just return the string as-is
                pass
            
            return value
        
        # For any other type, convert to string
        return str(value)
    
    def value_from_datadict(self, data, files, name):
        """
        Convert comma-separated string back to list of tags.
        
        Args:
            data: Form data dictionary
            files: Uploaded files dictionary
            name: Field name
            
        Returns:
            List of cleaned tags
        """
        value = data.get(name, '')
        if not value:
            return '[]'  # Return empty JSON array string
        
        # Split by comma and clean each tag
        tags = [tag.strip() for tag in str(value).split(',') if tag.strip()]
        
        # Limit to 4 tags as specified
        tags = tags[:4]
        
        # Return as JSON string because JSONField.bound_data expects a string to parse
        import json
        return json.dumps(tags)
    
    class Media:
        css = {
            'all': ('licenses/css/tags_input.css',)
        }
        js = ('licenses/js/tags_input.js',)
