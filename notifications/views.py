"""Admin pages of the notification system.

Both pages are registered on the default admin site through
``ok_tools.admin``; they are ordinary admin views, not a separate site.
"""

from django.apps import apps
from django.contrib import messages
from django.contrib.admin.sites import site as default_site
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.middleware.csrf import get_token
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext
from notifications import config
from notifications import links
from notifications import presets
from django.contrib.auth import get_user_model
from notifications import registry
from notifications import selectors
from notifications import stats
from notifications.models import NotificationConfig
from notifications.models import NotificationEventTypeConfig
from notifications.services import delegate
from notifications.services import mark_done
from notifications.services import reopen
from notifications.services import revoke_delegation
from notifications.services import snooze
from notifications.services import suppress_events
from notifications.services import wake
from typing import List
import logging


logger = logging.getLogger('django')


PAGE_SIZE = 50

PAYLOAD_LABELS = {
    'channel': _('Channel'),
    'confirmed': _('Confirmed'),
    'cover_available': _('Cover available'),
    'count': _('Count'),
    'created_at': _('Created'),
    'date': _('Date'),
    'days_late': _('Days late'),
    'deviation': _('Difference'),
    'discovered_at': _('Discovered'),
    'due_at': _('Due'),
    'email': _('Email address'),
    'error': _('Error'),
    'filename': _('File'),
    'free_gb': _('Free space (GB)'),
    'free_percent': _('Free space (%)'),
    'issue': _('Issue'),
    'item': _('Equipment'),
    'job': _('Job'),
    'live': _('Live broadcast'),
    'name': _('Name'),
    'number': _('Number'),
    'operation': _('Operation'),
    'overdue': _('Overdue'),
    'path': _('Path'),
    'project_name': _('Project'),
    'reel_available': _('Reel available'),
    'scheduled_at': _('Scheduled for'),
    'severity': _('Severity'),
    'start': _('Start'),
    'status': _('Status'),
    'storage': _('Storage'),
    'room': _('Room'),
    'task': _('Task'),
    'title': _('Title'),
    'uploaded_at': _('Uploaded'),
    'user': _('Person'),
    'video_available': _('Video available'),
}

# Types that can hand over the finished work screen instead of the object.
# "Planned own production without a reel" asks for one render, so the entry
# offers the prefilled Reel Studio right away.
REEL_ACTION_TYPES = ('media_files.missing_reel',)

# The feed is not a separate list without actions: it is the "everything"
# state of the same list, so the same bulk actions apply.
VIEW_OPEN = 'open'
VIEW_SNOOZED = 'snoozed'
VIEW_HANDLED = 'handled'
VIEW_DELEGATED = 'delegated'
VIEW_ALL = 'all'
VIEWS = (VIEW_OPEN, VIEW_SNOOZED, VIEW_HANDLED, VIEW_DELEGATED, VIEW_ALL)


def _redirect(name: str, query: str = '') -> HttpResponseRedirect:
    """Redirect back to one of the notification pages, keeping the filters."""
    url = reverse(f'admin:{name}')
    return HttpResponseRedirect(f'{url}?{query}' if query else url)


def _delegate_target(request):
    """Return the staff member picked as the delegation target, or None."""
    raw = (request.POST.get('delegate_to') or '').strip()
    if not raw.isdigit():
        return None
    User = get_user_model()
    return User.objects.filter(
        pk=int(raw), is_active=True, is_staff=True).first()


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
            queryset = selectors.snoozed_action_items(user, request, filters)
        elif view == VIEW_HANDLED:
            queryset = selectors.handled_action_items(user, request, filters)
        elif view == VIEW_DELEGATED:
            queryset = selectors.delegated_action_items(user, request, filters)
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


def _display_value(value):
    """Return a compact, JSON-safe value for the detail drawer."""
    if isinstance(value, bool):
        return str(_('Yes') if value else _('No'))
    if value in (None, ''):
        return str(_('Not specified'))
    return str(value)


def _payload_details(payload):
    """Expose useful payload fields with translated labels, never raw JSON."""
    return [
        {
            'key': key,
            'label': str(PAYLOAD_LABELS.get(
                key, key.replace('_', ' ').capitalize())),
            'value': _display_value(value),
        }
        for key, value in (payload or {}).items()
        if key != 'url'
    ]


def _reel_action_urls(events) -> dict:
    """Return ``{event id: prefilled Reel Studio URL}`` for reel entries.

    Built while reading, never stored: the link carries the broadcast date
    and the source video, and both can still change after the notification
    was written.
    """
    urls = {}
    for event in events:
        if event.event_type not in REEL_ACTION_TYPES:
            continue
        url = links.reel_studio_url((event.payload or {}).get('number'))
        if url:
            urls[event.pk] = url
    return urls


def _serialize_event(event, status='', item=None, action_url=''):
    """Build the reader-language JSON contract consumed by the React page."""
    spec = event.event_type_spec
    category_labels = dict(registry.CATEGORY_CHOICES)
    state_labels = {
        'open': _('Open'),
        'snoozed': _('Postponed'),
        'handled': _('Handled'),
        'resolved': _('Automatically resolved'),
        '': _('For information'),
    }
    occurred_at = timezone.localtime(event.occurred_at)
    snoozed_until = getattr(item, 'snoozed_until', None)
    return {
        'id': event.pk,
        'selectable': True,
        'module': event.module,
        'moduleLabel': str(
            spec.module_label if spec else event.module),
        'eventType': event.event_type,
        'label': str(event.label),
        'message': event.message,
        'description': str(spec.description) if spec else '',
        'category': event.category,
        'categoryLabel': str(category_labels.get(
            event.category, event.category)),
        'occurredAt': occurred_at.isoformat(),
        'occurredAtLabel': occurred_at.strftime('%d.%m.%Y %H:%M'),
        'status': status,
        'statusLabel': str(state_labels.get(status, status)),
        'snoozedUntil': (
            timezone.localtime(snoozed_until).strftime('%d.%m.%Y %H:%M')
            if snoozed_until else ''),
        'url': event.url,
        'actionUrl': action_url,
        'actionLabel': str(_('Create reel')) if action_url else '',
        'objectId': event.object_id,
        'details': _payload_details(event.payload),
        'delegatedTo': _user_label(getattr(item, 'delegated_to', None)),
        'delegatedBy': _user_label(getattr(item, 'delegated_by', None)),
    }


def _user_label(user):
    """Return a readable name for a delegation partner, or ''.

    The name lives on the profile, not on the user row, so a list built from
    ``get_full_name`` alone would show nothing but e-mail addresses.
    """
    if user is None:
        return ''
    profile = getattr(user, 'profile', None)
    first = (getattr(profile, 'first_name', '') or '').strip()
    last = (getattr(profile, 'last_name', '') or '').strip()
    name = ' '.join(part for part in (first, last) if part)
    if not name:
        name = (user.get_full_name() or '').strip()
    if not name:
        return user.email
    # Keep the address as a disambiguator: two colleagues can share a name.
    return f'{name} ({user.email})' if user.email else name


def _serialize_rows(user, rows, events_only=False):
    """Serialize event querysets and personal item querysets consistently."""
    rows = list(rows)
    events = [row if events_only else row.event for row in rows]
    statuses = selectors.status_by_event(user, events)
    action_urls = _reel_action_urls(events)
    return [
        _serialize_event(
            event,
            status=statuses.get(event.pk, ''),
            item=None if events_only else row,
            action_url=action_urls.get(event.pk, ''),
        )
        for row, event in zip(rows, events)
    ]


def _serialize_expectations(groups):
    """Build compact expectation cards and their expandable details."""
    category_labels = dict(registry.CATEGORY_CHOICES)
    result = []
    for group in groups:
        spec = registry.get(group['code'])
        result.append({
            'code': group['code'],
            'label': str(group['label']),
            'module': group['module'],
            'moduleLabel': str(group['module_label']),
            'category': group['category'],
            'categoryLabel': str(category_labels.get(
                group['category'], group['category'])),
            'description': str(spec.description) if spec else '',
            'count': len(group['items']),
            'items': [
                {
                    'message': item['message'],
                    'url': item['url'],
                    'details': _payload_details(item['payload']),
                }
                for item in group['items']
            ],
        })
    return result


def _serialize_expectation_rows(groups):
    """Flatten live expectations into read-only rows for the overview card."""
    rows = []
    for group in groups:
        for index, item in enumerate(group['items']):
            detail_values = {
                detail['key']: detail['value'] for detail in item['details']}
            time_label = next((
                detail_values[key]
                for key in ('due_at', 'date', 'scheduled_at', 'start')
                if detail_values.get(key)
            ), str(_('Today')))
            rows.append({
                'id': f"expectation:{group['code']}:{index}",
                'selectable': False,
                'module': group['module'],
                'moduleLabel': group['moduleLabel'],
                'eventType': group['code'],
                'label': group['label'],
                'message': item['message'],
                'description': group['description'],
                'category': group['category'],
                'categoryLabel': group['categoryLabel'],
                'occurredAt': '',
                'occurredAtLabel': time_label,
                'status': 'expected',
                'statusLabel': str(_('Expected')),
                'snoozedUntil': '',
                'url': item['url'],
                'actionUrl': '',
                'actionLabel': '',
                'objectId': '',
                'details': item['details'],
            })
    return rows


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
        elif action == 'delegate':
            to_user = _delegate_target(request)
            if to_user is None:
                messages.warning(
                    request, _('Select the colleague to delegate to.'))
            else:
                handed = delegate(
                    user, _selected_ids(request, user, filters), to_user)
                if handed:
                    messages.success(request, ngettext(
                        '%(count)d entry was delegated to %(name)s.',
                        '%(count)d entries were delegated to %(name)s.',
                        handed) % {
                            'count': handed,
                            'name': _user_label(to_user)})
                else:
                    messages.warning(request, _('Nothing was delegated.'))
        elif action == 'revoke_delegation':
            taken_back = revoke_delegation(
                user, _selected_ids(request, user, filters))
            if taken_back:
                messages.success(request, ngettext(
                    '%(count)d entry was taken back.',
                    '%(count)d entries were taken back.',
                    taken_back) % {'count': taken_back})
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
    snoozed_items = selectors.snoozed_action_items(user, request, filters)
    handled_items = selectors.handled_action_items(user, request, filters)
    delegated_items = selectors.delegated_action_items(user, request, filters)

    if view == VIEW_SNOOZED:
        rows = snoozed_items
    elif view == VIEW_HANDLED:
        rows = handled_items
    elif view == VIEW_DELEGATED:
        rows = delegated_items
    elif view == VIEW_ALL:
        rows = selectors.feed(user, request, limit=0, filters=filters)
    else:
        rows = open_items

    paginator = Paginator(rows, PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    serialized_rows = _serialize_rows(
        user, page.object_list, events_only=view == VIEW_ALL)

    expectation_groups = selectors.expectations(user, request)
    serialized_expectations = _serialize_expectations(expectation_groups)

    # The counter has to be read before the marker is moved.
    state = selectors.get_state(user)
    new_count = selectors.new_count(user, request)
    overview_open_items = selectors.open_action_items(user, request)
    overview_snoozed_items = selectors.snoozed_action_items(user, request)
    overview_handled_items = selectors.handled_action_items(user, request)
    overview_problem_events = selectors.active_problem_events(user, request)
    overview_new_events = selectors.feed(
        user, request, limit=PAGE_SIZE, since=state.last_seen_at)
    overview_delegated_items = selectors.delegated_action_items(user, request)
    counts = {
        'open': overview_open_items.count(),
        'snoozed': overview_snoozed_items.count(),
        'handled': overview_handled_items.count(),
        'delegated': overview_delegated_items.count(),
        'problems': overview_problem_events.count(),
    }
    filter_context = _filter_context(user, request, filters)
    user_name = user.get_full_name() or getattr(user, 'email', '') or str(user)
    notifications_data = {
        'csrfToken': get_token(request),
        'rows': serialized_rows,
        'expectations': serialized_expectations,
        'overviewRows': {
            'expected': _serialize_expectation_rows(
                serialized_expectations),
            'new': _serialize_rows(
                user, overview_new_events, events_only=True),
            'action': _serialize_rows(
                user, overview_open_items[:PAGE_SIZE]),
            'snoozed': _serialize_rows(
                user, overview_snoozed_items[:PAGE_SIZE]),
            'problems': _serialize_rows(
                user, overview_problem_events[:PAGE_SIZE], events_only=True),
        },
        'stats': {
            'expected': sum(group['count'] for group in serialized_expectations),
            'new': new_count,
            **counts,
        },
        'view': view,
        # Only staff can act on notifications, so only staff can receive one.
        'colleagues': [
            {'id': colleague.pk, 'name': _user_label(colleague)}
            for colleague in get_user_model().objects
            .filter(is_active=True, is_staff=True)
            .exclude(pk=user.pk)
            .select_related('profile')
            .order_by('profile__last_name', 'profile__first_name', 'email')[:200]
        ],
        'shownCount': paginator.count,
        'totalActionCount': selectors.action_count(user, request),
        'hasSubscriptions': bool(selectors.subscribed_types(user, request)),
        'filterQuery': request.GET.urlencode(),
        'filters': {
            'module': filters.get('module', ''),
            'type': filters.get('type', ''),
            'category': filters.get('category', ''),
            'older': filters.get('older', ''),
            'dateFrom': (
                filters['date_from'].isoformat()
                if filters.get('date_from') else ''),
            'dateTo': (
                filters['date_to'].isoformat()
                if filters.get('date_to') else ''),
        },
        'filterOptions': {
            'modules': [
                {'value': option['value'], 'label': str(option['label'])}
                for option in filter_context['filter_modules']
            ],
            'types': [
                {'value': option['value'], 'label': str(option['label'])}
                for option in filter_context['filter_types']
            ],
            'categories': [
                {'value': value, 'label': str(label)}
                for value, label in registry.CATEGORY_CHOICES
            ],
        },
        'pagination': {
            'number': page.number,
            'pages': paginator.num_pages,
            'hasPrevious': page.has_previous(),
            'previous': page.previous_page_number() if page.has_previous() else None,
            'hasNext': page.has_next(),
            'next': page.next_page_number() if page.has_next() else None,
        },
        'urls': {
            'feed': reverse('admin:notifications_feed'),
            'subscriptions': reverse('admin:notifications_subscriptions'),
            'settings': (
                reverse('admin:notifications_settings')
                if user.is_superuser else ''),
            'stats': (
                reverse('admin:notifications_stats')
                if user.is_superuser else ''),
            'admin': reverse('admin:index'),
        },
        'user': {
            'name': user_name,
            'email': getattr(user, 'email', ''),
            'initials': ''.join(
                part[0] for part in user_name.split()[:2]).upper(),
            'isSuperuser': user.is_superuser,
        },
        'i18n': {
            'title': str(_('Notification center')),
            'subtitle': str(_('Everything important for today at a glance.')),
            'todayOverview': str(_("Today's overview")),
            'expectedToday': str(_('Expected today')),
            'newSinceVisit': str(_('New since last visit')),
            'actionRequired': str(_('Action required')),
            'postponed': str(_('Postponed')),
            'problems': str(_('Problems')),
            'search': str(_('Search notifications…')),
            'filters': str(_('Filters')),
            'module': str(_('Module')),
            'eventType': str(_('Event type')),
            'category': str(_('Category')),
            'period': str(_('Period')),
            'from': str(_('From')),
            'to': str(_('To')),
            'olderThan': str(_('Older than (days)')),
            'applyFilters': str(_('Apply filters')),
            'reset': str(_('Reset')),
            'all': str(_('All')),
            'open': str(_('Open')),
            'handled': str(_('Handled')),
            'chronicle': str(_('Chronicle')),
            'status': str(_('Status')),
            'subject': str(_('Subject / object')),
            'time': str(_('Time')),
            'state': str(_('State')),
            'actions': str(_('Actions')),
            'selectAllPage': str(_('Select all on this page')),
            'applyAll': str(_('Apply to all matching entries')),
            'markHandled': str(_('Mark as handled')),
            'postpone': str(_('Postpone until tomorrow')),
            'showAgain': str(_('Show again now')),
            'reopen': str(_('Reopen')),
            'suppress': str(_('Never report again')),
            'suppressConfirm': str(_(
                'These entries will never be reported again, for anyone. Continue?')),
            'results': str(_('results')),
            'noRows': str(_('No notifications match this view.')),
            'noSubscriptions': str(_(
                'You are not subscribed to any module yet.')),
            'chooseModules': str(_('Choose your modules')),
            'close': str(_('Close')),
            'todayExpectations': str(_("Today's expectations")),
            'noExpectations': str(_('Nothing is expected today.')),
            'viewItem': str(_('Open working screen')),
            'delegated': str(_('Delegated')),
            'delegate': str(_('Delegate')),
            'delegateTo': str(_('Delegate to…')),
            'delegatedTo': str(_('Delegated to')),
            'delegatedBy': str(_('Delegated by')),
            'takeBack': str(_('Take back')),
            'details': str(_('Details')),
            'description': str(_('Description')),
            'notification': str(_('Notification')),
            'settings': str(_('Settings')),
            'subscriptions': str(_('Subscriptions')),
            'statistics': str(_('Statistics')),
            'administration': str(_('Administration')),
            'previous': str(_('Previous')),
            'next': str(_('Next')),
            'page': str(_('Page')),
            'of': str(_('of')),
            'forInformation': str(_('For information')),
            'postponedUntil': str(_('Postponed until')),
            'showingOverview': str(_('Showing overview:')),
            'backToView': str(_('Back to current view')),
            'expected': str(_('Expected')),
        },
    }
    context = {
        **default_site.each_context(request),
        **filter_context,
        'title': _('My notifications'),
        'notifications_data': notifications_data,
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
                if spec.kind == 'storage_locations':
                    params[spec.name] = [
                        int(value) for value in request.POST.getlist(field)
                        if value.isdigit()
                    ]
                    continue
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
    storage_locations = []
    if apps.is_installed('media_files'):
        from media_files.models import StorageLocation

        storage_locations = list(
            StorageLocation.objects.filter(is_active=True).order_by(
                'storage_type', 'name'))
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
                        'kind': param.kind,
                        'choices': [
                            {
                                'value': location.pk,
                                'label': str(location),
                                'selected': location.pk in set(
                                    effective.get(param.name, [])),
                            }
                            for location in storage_locations
                        ] if param.kind == 'storage_locations' else [],
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
