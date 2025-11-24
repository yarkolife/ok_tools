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
        # Force default language if not set in session
        # This prevents Accept-Language header from overriding default language
        if not request.session.get('django_language'):
            # No language saved in session - force default language
            translation.activate(settings.LANGUAGE_CODE)
            request.LANGUAGE_CODE = settings.LANGUAGE_CODE
            # Save to session so it persists
            request.session['django_language'] = settings.LANGUAGE_CODE
        
        response = self.get_response(request)
        return response

