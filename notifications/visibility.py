"""Visibility of events, mirroring what the admin itself shows.

Subscribing to a module must never widen access. Django model permissions
cannot be queried directly here: a few ModelAdmins grant access on
``is_staff`` regardless of permissions, ``tools`` requires a superuser, and
staff permissions are filled in by hand. Asking the ModelAdmin itself keeps
event visibility identical to section visibility by construction.
"""

from django.apps import apps
from django.contrib import admin
from django.http import HttpRequest
from notifications import registry
from typing import List
from typing import Optional


def permission_request(user) -> HttpRequest:
    """Build a minimal request carrying the user, for permission checks."""
    request = HttpRequest()
    request.method = 'GET'
    request.user = user
    return request


def _resolve_model(event_type: registry.EventType):
    """Return the model class declared by the event type, or None."""
    if not event_type.model:
        return None
    try:
        return apps.get_model(event_type.model)
    except LookupError:
        # The owning app is not installed in this deployment.
        return None


def can_view(user, event_type: registry.EventType,
             request: Optional[HttpRequest] = None) -> bool:
    """Return whether the user may see events of this type."""
    if not user or not user.is_authenticated or not user.is_staff:
        return False
    if event_type.superuser_only:
        return bool(user.is_superuser)
    if user.is_superuser:
        return True

    model = _resolve_model(event_type)
    if model is None:
        # No model to mirror: staff level access is the best available gate.
        return True

    model_admin = admin.site._registry.get(model)
    if model_admin is None:
        return True

    return bool(model_admin.has_view_permission(
        request or permission_request(user)))


def visible_codes(user, event_types: List[registry.EventType],
                  request: Optional[HttpRequest] = None) -> List[str]:
    """Return the codes of the given types the user is allowed to see."""
    check_request = request or permission_request(user)
    return [
        event_type.code
        for event_type in event_types
        if can_view(user, event_type, check_request)
    ]
