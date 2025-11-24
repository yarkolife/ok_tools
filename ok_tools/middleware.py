"""Custom middleware for OK Tools."""

from django.conf import settings
from django.utils import translation


class ForceDefaultLanguageMiddleware:
    """
    Middleware to force default language (LANGUAGE_CODE) when no language is saved in session.
    
    This prevents LocaleMiddleware from using Accept-Language header from browser,
    ensuring consistent default language across all users.
    """
    
    def __init__(self, get_response):
        """Initialize middleware with get_response."""
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Force default language if no language is set in session.
        
        LocaleMiddleware sets language in this order:
        1. URL language (if i18n_patterns used)
        2. Session language
        3. Cookie language
        4. Accept-Language header
        5. LANGUAGE_CODE from settings
        
        This middleware runs after LocaleMiddleware and ensures that if no language
        was saved in session, we use LANGUAGE_CODE instead of Accept-Language.
        """
        # Check if language is already set (by LocaleMiddleware)
        current_language = translation.get_language()
        
        # If no language in session and current language doesn't match LANGUAGE_CODE,
        # force LANGUAGE_CODE (this happens when Accept-Language was used)
        if not request.session.get('django_language'):
            # Language was likely set from Accept-Language header
            # Force default language from settings
            if current_language != settings.LANGUAGE_CODE:
                translation.activate(settings.LANGUAGE_CODE)
                request.LANGUAGE_CODE = settings.LANGUAGE_CODE
        
        response = self.get_response(request)
        return response

