"""Custom middleware for OK Tools."""

from django.conf import settings
from django.utils import translation


class ForceDefaultLanguageMiddleware:
    """
    Middleware to initialize session language before LocaleMiddleware.

    If no language is saved in session yet, it derives language from standard
    Django language detection (URL/cookie/Accept-Language) and falls back to
    LANGUAGE_CODE.
    """
    
    def __init__(self, get_response):
        """Initialize middleware with get_response."""
        self.get_response = get_response
    
    def __call__(self, request):
        """
        Initialize language in session if not set.
        
        This middleware runs AFTER SessionMiddleware but BEFORE LocaleMiddleware to ensure that:
        1. Session is already initialized by SessionMiddleware
        2. If no language is saved in session, we derive one from request
        3. LocaleMiddleware will then use session language for consistency
        
        LocaleMiddleware checks language in this order:
        1. URL language (if i18n_patterns used)
        2. Session language (we set this here)
        3. Cookie language
        4. Accept-Language header
        5. LANGUAGE_CODE from settings
        """
        # Session should be initialized by SessionMiddleware at this point.
        if hasattr(request, 'session'):
            session_language = request.session.get('django_language')
            if not session_language:
                # No language saved in session.
                # Respect Django standard detection for the current request.
                detected_language = translation.get_language_from_request(
                    request,
                    check_path=False,
                )
                normalized_language = (
                    detected_language.lower().split('-')[0]
                    if detected_language
                    else settings.LANGUAGE_CODE
                )

                request.session['django_language'] = normalized_language
                # Mark session as modified so it gets saved
                request.session.modified = True
                # Activate language immediately for this request
                translation.activate(normalized_language)
                request.LANGUAGE_CODE = normalized_language
            else:
                # Language is in session - activate it for this request
                translation.activate(session_language)
                request.LANGUAGE_CODE = session_language
        
        response = self.get_response(request)
        return response
