from threading import local


_thread_locals = local()


class CurrentUserMiddleware:
    """Middleware to store current user in thread local storage."""

    def __init__(self, get_response):
        """Initialize middleware with get_response."""
        self.get_response = get_response

    def __call__(self, request):
        """Store user before request and clean up after response."""
        _thread_locals.user = getattr(request, 'user', None)
        response = self.get_response(request)
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user
        return response


def get_current_user():
    """Get current user from thread local storage."""
    return getattr(_thread_locals, 'user', None)
