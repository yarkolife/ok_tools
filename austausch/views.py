"""Views for Austausch module."""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

from .models import ExchangeItem


def check_austausch_enabled():
    """Check if Austausch module is enabled."""
    if not getattr(settings, 'AUSTAUSCH_ENABLED', False):
        raise ImproperlyConfigured(
            _('Austausch module is disabled. Set AUSTAUSCH_ENABLED=true to enable.')
        )


class ExchangeFeedView(UserPassesTestMixin, LoginRequiredMixin, ListView):
    """Display exchange items feed. Only accessible to staff members."""
    
    model = ExchangeItem
    template_name = 'austausch/feed_admin.html'  # Use admin template without sidebar
    context_object_name = 'exchange_items'
    paginate_by = 20
    
    def test_func(self):
        """Check if user is staff member."""
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def dispatch(self, request, *args, **kwargs):
        """Check if module is enabled before processing request."""
        check_austausch_enabled()
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get filtered queryset based on request parameters."""
        # Only show video items (PDF is part of package, not shown separately)
        qs = ExchangeItem.objects.filter(file_type='video')
        
        # Filter by channel
        channel = self.request.GET.get('channel')
        if channel:
            qs = qs.filter(channel=channel)
        
        # Filter by date (items discovered after this date)
        date_from = self.request.GET.get('date_from')
        if date_from:
            try:
                from django.utils.dateparse import parse_datetime, parse_date
                # Try datetime first
                dt = parse_datetime(date_from)
                if dt:
                    qs = qs.filter(discovered_at__gte=dt)
                else:
                    # Try date
                    d = parse_date(date_from)
                    if d:
                        from django.utils import timezone
                        qs = qs.filter(discovered_at__date__gte=d)
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore filter
        
        # Filter by status
        status = self.request.GET.get('status')
        if status in ['new', 'imported', 'failed']:
            qs = qs.filter(import_status=status)
        
        # Filter by OK-Tools managed
        oktools_only = self.request.GET.get('oktools_only')
        if oktools_only and oktools_only.lower() == 'true':
            qs = qs.filter(is_oktools_managed=True)
        
        # Filter by legacy
        legacy_only = self.request.GET.get('legacy_only')
        if legacy_only and legacy_only.lower() == 'true':
            qs = qs.filter(is_legacy=True)
        
        # Search by title/description/sender
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(filename__icontains=search) |
                Q(sendeverantwortung__icontains=search)
            )
        
        return qs.order_by('-discovered_at')
    
    def get_context_data(self, **kwargs):
        """Add additional context data."""
        context = super().get_context_data(**kwargs)
        
        # Get distinct channels for filter dropdown
        context['channels'] = ExchangeItem.objects.values_list(
            'channel', flat=True
        ).distinct().order_by('channel')
        
        # Get filter values from request
        context['current_channel'] = self.request.GET.get('channel', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['oktools_only'] = self.request.GET.get('oktools_only', '')
        context['legacy_only'] = self.request.GET.get('legacy_only', '')
        context['search'] = self.request.GET.get('search', '')
        
        # Statistics
        context['total_items'] = ExchangeItem.objects.count()
        context['new_items'] = ExchangeItem.objects.filter(import_status='new').count()
        context['imported_items'] = ExchangeItem.objects.filter(import_status='imported').count()
        context['oktools_items'] = ExchangeItem.objects.filter(is_oktools_managed=True).count()
        
        return context

