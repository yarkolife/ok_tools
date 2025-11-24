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
        Force default language in session if not set.
        
        This middleware runs BEFORE LocaleMiddleware to ensure that:
        1. If no language is saved in session, we set LANGUAGE_CODE in session
        2. LocaleMiddleware will then use session language instead of Accept-Language header
        
        LocaleMiddleware checks language in this order:
        1. URL language (if i18n_patterns used)
        2. Session language (we set this here)
        3. Cookie language
        4. Accept-Language header
        5. LANGUAGE_CODE from settings
        """
        # Ensure session is initialized
        if not hasattr(request, 'session'):
            request.session = {}
        
        # Force default language in session if not set
        # This prevents LocaleMiddleware from using Accept-Language header
        if not request.session.get('django_language'):
            # No language saved in session - set default language
            request.session['django_language'] = settings.LANGUAGE_CODE
            # Mark session as modified so it gets saved
            request.session.modified = True
        
        response = self.get_response(request)
        return response

