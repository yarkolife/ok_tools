"""DRF authentication class for playout integration API endpoints."""

from django.utils.translation import gettext_lazy as _
from planung.models import PlanungConfig
from rest_framework.authentication import BaseAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed


class PlayoutApiKeyAuthentication(BaseAuthentication):
    """Authenticate playout requests using DRF tokens or the legacy shared key.

    Tokens managed at ``/admin/authtoken/token/`` are accepted in either the
    ``X-API-Key`` header or the ``Authorization`` header.

    The legacy ``PlanungConfig.playout_import_api_key`` shared secret remains
    valid for existing integrations.
    """

    keyword = "X-API-Key"

    def authenticate(self, request):
        """Return authenticated DRF token user or legacy key on success."""
        api_key = self._extract_key(request)
        if not api_key:
            raise AuthenticationFailed(
                _("Authentication credentials were not provided. "
                  "Send X-API-Key header or Authorization: Bearer <token>.")
            )

        token = Token.objects.select_related("user").filter(key=api_key).first()
        if token:
            if not token.user.is_active:
                raise AuthenticationFailed(_("User inactive or deleted."))
            return (token.user, token)

        legacy_key = PlanungConfig.get_config().playout_import_api_key
        if legacy_key and api_key == legacy_key:
            return (None, api_key)

        raise AuthenticationFailed(_("Invalid API key."))

    def authenticate_header(self, request):
        """Return string for WWW-Authenticate header on 401 responses."""
        return self.keyword

    def _extract_key(self, request):
        """Extract API key from X-API-Key, Bearer, or Token auth headers."""
        x_api_key = request.META.get("HTTP_X_API_KEY", "")
        if x_api_key:
            return x_api_key.strip()

        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        lower_auth_header = auth_header.lower()
        if lower_auth_header.startswith("bearer "):
            return auth_header[7:].strip()
        if lower_auth_header.startswith("token "):
            return auth_header[6:].strip()

        return ""
