from .services.user_service import UserService
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse


def is_admin(user):
    """Check if user is admin."""
    return user.is_authenticated and user.is_staff


@login_required
@user_passes_test(is_admin)
def api_users_statistics(request):
    """API endpoint for users statistics."""
    user_service = UserService()
    result = user_service.get_users_statistics(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_recent_users(request):
    """API endpoint for recent user activities."""
    user_service = UserService()
    result = user_service.get_recent_users(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)


@login_required
@user_passes_test(is_admin)
def api_users_detail(request):
    """API endpoint for detailed users data."""
    user_service = UserService()
    result = user_service.get_users_detail(request)
    
    if result['success']:
        return JsonResponse(result)
    else:
        return JsonResponse(result, status=500)