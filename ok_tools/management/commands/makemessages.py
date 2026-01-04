"""
Custom makemessages command that recognizes _p as alias for ngettext.

This command extends Django's makemessages to support the _p() alias
used for plural translations in the codebase.
"""

from django.core.management.commands.makemessages import Command as BaseCommand


class Command(BaseCommand):
    """Custom makemessages command with support for _p() alias."""
    
    def __init__(self, *args, **kwargs):
        """Initialize the command and set up xgettext_options."""
        super().__init__(*args, **kwargs)
        # Initialize xgettext_options if not already set
        if not hasattr(self, 'xgettext_options') or self.xgettext_options is None:
            self.xgettext_options = []
        
        # Convert to list if it's not already
        if not isinstance(self.xgettext_options, list):
            self.xgettext_options = list(self.xgettext_options)
        
        # Add keyword for _p if not already present
        # Format: --keyword=_p:1,2 means _p function with translatable strings at positions 1 and 2
        keyword_added = False
        for opt in self.xgettext_options:
            if isinstance(opt, str) and opt.startswith('--keyword=_p'):
                keyword_added = True
                break
        
        if not keyword_added:
            self.xgettext_options.append('--keyword=_p:1,2')
    
    def handle(self, *args, **options):
        """Handle the command with custom xgettext options."""
        # Ensure xgettext_options is set correctly (in case it was reset)
        if not hasattr(self, 'xgettext_options') or self.xgettext_options is None:
            self.xgettext_options = []
        
        if not isinstance(self.xgettext_options, list):
            self.xgettext_options = list(self.xgettext_options)
        
        # Add keyword for _p if not already present
        keyword_added = False
        for opt in self.xgettext_options:
            if isinstance(opt, str) and opt.startswith('--keyword=_p'):
                keyword_added = True
                break
        
        if not keyword_added:
            self.xgettext_options.append('--keyword=_p:1,2')
        
        # Call parent handle method
        return super().handle(*args, **options)

