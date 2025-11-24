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
        
        This middleware runs AFTER SessionMiddleware but BEFORE LocaleMiddleware to ensure that:
        1. Session is already initialized by SessionMiddleware
        2. If no language is saved in session, we set LANGUAGE_CODE in session
        3. LocaleMiddleware will then use session language instead of Accept-Language header
        
        LocaleMiddleware checks language in this order:
        1. URL language (if i18n_patterns used)
        2. Session language (we set this here)
        3. Cookie language
        4. Accept-Language header
        5. LANGUAGE_CODE from settings
        """
        # Session should be initialized by SessionMiddleware at this point
        # Force default language in session if not set
        # This prevents LocaleMiddleware from using Accept-Language header
        if hasattr(request, 'session'):
            session_language = request.session.get('django_language')
            if not session_language:
                # No language saved in session - set default language
                request.session['django_language'] = settings.LANGUAGE_CODE
                # Mark session as modified so it gets saved
                request.session.modified = True
                # Activate language immediately for this request
                translation.activate(settings.LANGUAGE_CODE)
                request.LANGUAGE_CODE = settings.LANGUAGE_CODE
            else:
                # Language is in session - activate it for this request
                translation.activate(session_language)
                request.LANGUAGE_CODE = session_language
        
        response = self.get_response(request)
        return response

