"""Admin pages of the notification system.

Both pages are registered on the default admin site through
``ok_tools.admin``; they are ordinary admin views, not a separate site.
"""

from django.contrib import messages
from django.contrib.admin.sites import site as default_site
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from notifications import config
from notifications import presets
from notifications import registry
from notifications import selectors
from notifications import stats
from notifications.models import NotificationConfig
from notifications.models import NotificationEventTypeConfig
from notifications.services import mark_done
from notifications.services import reopen
from notifications.services import snooze
from notifications.services import suppress_events
from notifications.services import wake
from typing import List
import logging


logger = logging.getLogger('django')


PAGE_SIZE = 50

# The feed is not a separate list without actions: it is the "everything"
# state of the same list, so the same bulk actions apply.
VIEW_OPEN = 'open'
VIEW_SNOOZED = 'snoozed'
VIEW_HANDLED = 'handled'
VIEW_ALL = 'all'
VIEWS = (VIEW_OPEN, VIEW_SNOOZED, VIEW_HANDLED, VIEW_ALL)


def _redirect(name: str, query: str = '') -> HttpResponseRedirect:
    """Redirect back to one of the notification pages, keeping the filters."""
    url = reverse(f'admin:{name}')
    return HttpResponseRedirect(f'{url}?{query}' if query else url)


def _selected_ids(request, user, filters) -> List[int]:
    """Return the event ids the form addresses.

    Either the ticked rows, or -- when the user asked for it -- everything
    that matches the current filters, which is the point of having filters.
    On the postponed view "everything" means the postponed items: the open
    list is empty there by definition.
    """
    if request.POST.get('select_all') == '1':
        view = request.POST.get('view', VIEW_OPEN)
        if view == VIEW_SNOOZED:
            queryset = selectors.snoozed_action_items(user, request)
        elif view == VIEW_HANDLED:
            queryset = selectors.handled_action_items(user, request, filters)
        elif view == VIEW_ALL:
            return list(
                selectors.feed(user, request, limit=0, filters=filters)
                .values_list('id', flat=True)
            )
        else:
            queryset = selectors.open_action_items(user, request, filters)
        return list(queryset.values_list('event_id', flat=True))
    return [
        int(value) for value in request.POST.getlist('event_ids')
        if value.isdigit()
    ]


def _filter_context(user, request, filters):
    """Build the choices and the current values of the filter form."""
    types = selectors.allowed_types(user, request)
    modules = []
    for event_type in types:
        if event_type.module not in [item['value'] for item in modules]:
            modules.append({
                'value': event_type.module,
                'label': event_type.module_label,
            })
    return {
        'filter_modules': modules,
        'filter_types': [
            {'value': event_type.code, 'label': event_type.label}
            for event_type in types
        ],
        'filter_categories': registry.CATEGORY_CHOICES,
        'filters': filters,
        'filter_query': request.GET.urlencode(),
        'has_filters': bool(filters),
    }


def feed_view(request):
    """Show the personal feed, the action items and the subscriptions."""
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action', '')
        query = request.POST.get('filter_query', '')
        filters = selectors.parse_filters_from_query(query)

        if action == 'done':
            changed = mark_done(user, _selected_ids(request, user, filters))
            if changed:
                messages.success(request, ngettext(
                    '%(count)d entry marked as handled.',
                    '%(count)d entries marked as handled.',
                    changed) % {'count': changed})
            else:
                messages.warning(request, _('Nothing was selected.'))
        elif action == 'snooze':
            postponed = snooze(user, _selected_ids(request, user, filters))
            if postponed:
                messages.success(request, ngettext(
                    '%(count)d entry postponed until tomorrow.',
                    '%(count)d entries postponed until tomorrow.',
                    postponed) % {'count': postponed})
            else:
                messages.warning(request, _('Nothing was selected.'))
        elif action == 'reopen':
            reopened = reopen(user, _selected_ids(request, user, filters))
            if reopened:
                messages.success(request, ngettext(
                    '%(count)d entry was reopened.',
                    '%(count)d entries were reopened.',
                    reopened) % {'count': reopened})
            else:
                messages.warning(request, _('Nothing was selected.'))
        elif action == 'wake':
            woken = wake(user, _selected_ids(request, user, filters))
            if woken:
                messages.success(request, ngettext(
                    '%(count)d entry is shown again.',
                    '%(count)d entries are shown again.',
                    woken) % {'count': woken})
            else:
                messages.warning(request, _('Nothing was selected.'))
        elif action == 'suppress':
            silenced = suppress_events(
                _selected_ids(request, user, filters), user=user,
                reason=str(_('Silenced from the notification page')))
            if silenced:
                messages.success(request, ngettext(
                    '%(count)d entry will no longer be reported.',
                    '%(count)d entries will no longer be reported.',
                    silenced) % {'count': silenced})
            else:
                messages.warning(request, _('Nothing was selected.'))
        return _redirect('notifications_feed', query)

    filters = selectors.parse_filters(request)
    view = request.GET.get('view', VIEW_OPEN)
    if view not in VIEWS:
        view = VIEW_OPEN

    open_items = selectors.open_action_items(user, request, filters)
    snoozed_items = selectors.snoozed_action_items(user, request)
    handled_items = selectors.handled_action_items(user, request, filters)

    if view == VIEW_SNOOZED:
        rows = snoozed_items
    elif view == VIEW_HANDLED:
        rows = handled_items
    elif view == VIEW_ALL:
        rows = selectors.feed(user, request, limit=0, filters=filters)
    else:
        rows = open_items

    paginator = Paginator(rows, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    # The chronicle lists events, the other views list personal items; both
    # need the personal state so that nothing looks actionable when it is
    # already done.
    events = [
        row if view == VIEW_ALL else row.event for row in page.object_list]
    statuses = selectors.status_by_event(user, events)

    # The counter has to be read before the marker is moved.
    new_count = selectors.new_count(user, request)
    context = {
        **default_site.each_context(request),
        **_filter_context(user, request, filters),
        'title': _('My notifications'),
        'expectations': selectors.expectations(user, request),
        'page': page,
        'rows': [
            {
                'event': row if view == VIEW_ALL else row.event,
                'item': None if view == VIEW_ALL else row,
                'status': statuses.get(
                    (row if view == VIEW_ALL else row.event).pk, ''),
            }
            for row in page.object_list
        ],
        'view': view,
        'is_chronicle': view == VIEW_ALL,
        'counts': {
            'open': open_items.count(),
            'snoozed': snoozed_items.count(),
            'handled': handled_items.count(),
        },
        'shown_count': paginator.count,
        'total_action_count': selectors.action_count(user, request),
        'new_count': new_count,
        'has_subscriptions': bool(selectors.subscribed_types(user, request)),
        'subscriptions_url': reverse('admin:notifications_subscriptions'),
        'can_configure': user.is_superuser,
    }
    response = TemplateResponse(
        request, 'admin/notifications/feed.html', context)
    selectors.mark_seen(user)
    return response


def subscriptions_view(request):
    """Manage which modules and event types a staff member follows.

    Kept off the notification page: subscriptions are set once and then
    only take up room on a screen people look at every day.
    """
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'preset':
            applied = selectors.apply_preset(
                user, request.POST.get('preset', ''))
            if applied:
                messages.success(request, _('Subscriptions updated.'))
        elif action == 'subscriptions':
            selectors.set_subscriptions(
                user,
                request.POST.getlist('modules'),
                request.POST.getlist('codes'),
            )
            messages.success(request, _('Subscriptions updated.'))
        return _redirect('notifications_subscriptions')

    context = {
        **default_site.each_context(request),
        'title': _('My subscriptions'),
        'matrix': selectors.subscription_matrix(user, request),
        'presets': presets.choices(),
        'feed_url': reverse('admin:notifications_feed'),
    }
    return TemplateResponse(
        request, 'admin/notifications/subscriptions.html', context)


def settings_view(request):
    """Switch event types on and off and edit their parameters."""
    if not request.user.is_superuser:
        messages.error(
            request, _('Only superusers may configure notifications.'))
        return _redirect('notifications_feed')

    config.sync_event_type_configs()

    if request.method == 'POST':
        enabled_codes = set(request.POST.getlist('enabled'))
        rows = {
            row.code: row
            for row in NotificationEventTypeConfig.objects.all()
        }
        for event_type in registry.all_types():
            row = rows.get(event_type.code)
            if row is None:
                continue
            row.enabled = event_type.code in enabled_codes
            params = dict(row.params or {})
            for spec in event_type.params:
                field = f'param__{event_type.code}__{spec.name}'
                raw = request.POST.get(field, '')
                try:
                    params[spec.name] = int(raw)
                except (TypeError, ValueError):
                    params[spec.name] = spec.default
            row.params = params
            row.save(update_fields=['enabled', 'params'])
        messages.success(request, _('Notification settings saved.'))
        return _redirect('notifications_settings')

    stored = {
        row.code: row for row in NotificationEventTypeConfig.objects.all()}
    groups = []
    for module in registry.modules():
        entries = []
        for event_type in registry.all_types():
            if event_type.module != module:
                continue
            row = stored.get(event_type.code)
            effective = config.get_params(event_type.code)
            entries.append({
                'spec': event_type,
                'available': config.module_flag_enabled(event_type),
                'enabled': bool(row and row.enabled),
                'params': [
                    {
                        'name': param.name,
                        'label': param.label,
                        'help_text': param.help_text,
                        'value': effective.get(param.name, param.default),
                        'field': f'param__{event_type.code}__{param.name}',
                    }
                    for param in event_type.params
                ],
            })
        groups.append({
            'module': module,
            'module_label': registry.MODULE_LABELS.get(module, module),
            'entries': entries,
        })

    context = {
        **default_site.each_context(request),
        'title': _('Notification settings'),
        'groups': groups,
        'stats_url': reverse('admin:notifications_stats'),
        'config': NotificationConfig.get_config(),
        'config_url': reverse(
            'admin:notifications_notificationconfig_changelist'),
    }
    return TemplateResponse(
        request, 'admin/notifications/settings.html', context)


def stats_view(request):
    """Show whether the system is used: reads, closures and noise."""
    if not request.user.is_superuser:
        messages.error(
            request, _('Only superusers may see the notification statistics.'))
        return _redirect('notifications_feed')

    raw_days = request.GET.get('days', '')
    days = int(raw_days) if raw_days.isdigit() and int(raw_days) > 0 else 30
    report = stats.full_report(days)

    context = {
        **default_site.each_context(request),
        'title': _('Notification statistics'),
        'days': days,
        'summary': report['summary'],
        'types': report['types'],
        'users': report['users'],
        'feed_url': reverse('admin:notifications_feed'),
        'settings_url': reverse('admin:notifications_settings'),
    }
    return TemplateResponse(
        request, 'admin/notifications/stats.html', context)
