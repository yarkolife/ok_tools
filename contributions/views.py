from .models import Contribution
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import generic
from licenses.models import LicenseRequest


User = get_user_model()


@method_decorator(login_required, name='dispatch')
class ListContributionsView(generic.list.ListView):
    """List all contributions of the user."""

    template_name = 'contributions/list.html'
    model = Contribution

    def get_queryset(self):
        """List all contributions of the logged in user."""
        try:
            profile = self.request.user.profile
        except User.profile.RelatedObjectDoesNotExist:
            return

        licenses = LicenseRequest.objects.filter(profile=profile)
        contributions: list[Contribution] = []

        for license in licenses:
            contributions += Contribution.objects.filter(license=license)

        contributions.sort(key=lambda c: c.broadcast_date)
        return contributions
