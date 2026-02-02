from .disa_import import get_unique_dates
from .models import Contribution, DisaImport
from collections import defaultdict
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.views.decorators.http import require_http_methods
from licenses.models import License
from registration.models import Profile
import logging


User = get_user_model()
logger = logging.getLogger('django')


@method_decorator(login_required, name='dispatch')
class ListContributionsView(generic.list.ListView):
    """List all contributions of the user."""

    template_name = 'contributions/list.html'
    model = Contribution

    def get_context_data(self, **kwargs):
        """Group contributions by license for better display."""
        context = super().get_context_data(**kwargs)

        try:
            # Get profile through OKUser -> Profile relationship
            profile = Profile.objects.get(okuser=self.request.user)
        except Profile.DoesNotExist:
            context['grouped_contributions'] = {}
            context['stats'] = {
                'total_licenses': 0,
                'total_contributions': 0,
                'live_count': 0,
                'recorded_count': 0
            }
            return context

        # Get all contributions for user's licenses
        licenses = License.objects.filter(profile=profile)
        grouped_contributions = defaultdict(list)

        # Initialize counters
        total_contributions = 0
        live_count = 0
        recorded_count = 0

        for license in licenses:
            contributions = Contribution.objects.filter(license=license).order_by('-broadcast_date')
            if contributions.exists():
                grouped_contributions[license] = list(contributions)

                # Count contributions and types
                for contribution in contributions:
                    total_contributions += 1
                    if contribution.live:
                        live_count += 1
                    else:
                        recorded_count += 1

        # Sort licenses by latest contribution date
        sorted_groups = sorted(
            grouped_contributions.items(),
            key=lambda x: x[1][0].broadcast_date if x[1] else None,
            reverse=True
        )

        context['grouped_contributions'] = dict(sorted_groups)
        context['stats'] = {
            'total_licenses': len(grouped_contributions),
            'total_contributions': total_contributions,
            'live_count': live_count,
            'recorded_count': recorded_count
        }
        return context

    def get_queryset(self):
        """Return empty queryset since we handle data in get_context_data."""
        return Contribution.objects.none()


@staff_member_required
@require_http_methods(["POST"])
def extract_dates_from_file(request):
    """
    Extract unique dates from uploaded DISA export file.
    Used for AJAX request when adding new DisaImport.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    uploaded_file = request.FILES['file']
    
    try:
        dates = get_unique_dates(uploaded_file)
        dates_formatted = [
            {
                'value': date.strftime('%Y-%m-%d'),
                'label': date.strftime('%d.%m.%Y')
            }
            for date in dates
        ]
        return JsonResponse({
            'dates': dates_formatted,
            'count': len(dates)
        })
    except Exception as e:
        logger.error(f'Error extracting dates from file: {e}')
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["GET"])
def extract_dates_from_saved_file(request, pk):
    """
    Extract unique dates from saved DisaImport file.
    Used for AJAX request when editing existing DisaImport.
    """
    try:
        disa_import = DisaImport.objects.get(pk=pk)
        dates = get_unique_dates(disa_import.file)
        dates_formatted = [
            {
                'value': date.strftime('%Y-%m-%d'),
                'label': date.strftime('%d.%m.%Y')
            }
            for date in dates
        ]
        return JsonResponse({
            'dates': dates_formatted,
            'count': len(dates),
            'selected': disa_import.import_from_date.strftime('%Y-%m-%d') if disa_import.import_from_date else None
        })
    except DisaImport.DoesNotExist:
        return JsonResponse({'error': 'DisaImport not found'}, status=404)
    except Exception as e:
        logger.error(f'Error extracting dates from saved file: {e}')
        return JsonResponse({'error': str(e)}, status=500)


