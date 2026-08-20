"""Scan checks.

Every check receives its effective parameters and returns a list of
findings. Whether a finding is stored as an event or only rendered depends
on ``EventType.expectation``, not on the check itself.

Checks are only ever called for types that passed the gate chain, so they
may assume their module is installed.
"""

from datetime import timedelta
from django.apps import apps
from django.db.models import Count
from django.utils import timezone
from notifications import config
from notifications import links
from notifications.registry import Finding
from notifications.registry import scan_check
from notifications.utils import admin_url as _admin_url
from typing import Dict
from typing import List
import logging
# The declarations must be loaded before a check can attach itself to one;
# importing them here keeps that independent of import order elsewhere.
import notifications.event_types  # noqa: F401
import shutil


logger = logging.getLogger('django')


def _numbers_with_video(numbers) -> set:
    """Return the license numbers that have an available video file."""
    if not apps.is_installed('media_files'):
        return set()
    from media_files.utils import numbers_with_video

    return numbers_with_video(numbers)


# ---------------------------------------------------------------------------
# rental
# ---------------------------------------------------------------------------

def _rental_due(status: str, field: str, code: str,
                params: Dict[str, int]) -> List[Finding]:
    """Shared body of the two rental expectation checks."""
    RentalRequest = apps.get_model('rental.RentalRequest')
    horizon = max(int(params.get('horizon_days', 0)), 0)
    today = timezone.localdate()
    until = today + timedelta(days=horizon)
    queryset = (
        RentalRequest.objects
        .filter(status=status, **{
            f'{field}__date__gte': today,
            f'{field}__date__lte': until,
        })
        .exclude(rental_type='room')
        .select_related('user')
        .order_by(field)
    )
    findings = []
    for rental in queryset:
        moment = timezone.localtime(getattr(rental, field))
        findings.append(Finding(
            obj=rental,
            dedup_key=f'{code}|{rental.pk}|{moment:%Y-%m-%d}',
            payload={
                'project_name': rental.project_name,
                'user': str(rental.user),
                'due_at': moment.isoformat(),
                'overdue': moment.date() < timezone.localdate(),
                'url': links.rental_detail_url(rental.pk),
            },
        ))
    return findings


@scan_check('rental.pickup_due_today')
def check_pickup_due(params: Dict[str, int]) -> List[Finding]:
    """Find reservations whose pick-up date has been reached."""
    return _rental_due(
        'reserved', 'requested_start_date', 'rental.pickup_due_today', params)


@scan_check('rental.return_due_today')
def check_return_due(params: Dict[str, int]) -> List[Finding]:
    """Find issued rentals whose return date has been reached."""
    return _rental_due(
        'issued', 'requested_end_date', 'rental.return_due_today', params)


@scan_check('rental.room_due_today')
def check_room_due(params: Dict[str, int]) -> List[Finding]:
    """Find today's confirmed room bookings requiring staff presence."""
    RoomRental = apps.get_model('rental.RoomRental')
    today = timezone.localdate()
    now = timezone.now()
    queryset = (
        RoomRental.objects
        .filter(rental_request__status__in=('reserved', 'issued'))
        .select_related('room', 'rental_request__user')
        .order_by('requested_start_date',
                  'rental_request__requested_start_date')
    )
    findings = []
    for room_rental in queryset:
        start = room_rental.get_start_date()
        end = room_rental.get_end_date()
        if (start is None or end is None
                or timezone.localdate(start) != today or end <= now):
            continue
        rental = room_rental.rental_request
        local_start = timezone.localtime(start)
        findings.append(Finding(
            obj=room_rental,
            dedup_key=(
                f'rental.room_due_today|{room_rental.pk}'
                f'|{local_start:%Y-%m-%d}'),
            payload={
                'room': room_rental.room.name,
                'project_name': rental.project_name,
                'user': str(rental.user),
                'start': local_start.strftime('%H:%M'),
                'due_at': local_start.isoformat(),
                'url': links.rental_detail_url(rental.pk),
            },
        ))
    return findings


@scan_check('rental.pickup_overdue')
def check_pickup_overdue(params: Dict[str, int]) -> List[Finding]:
    """Find reservations whose agreed pick-up time has passed."""
    RentalRequest = apps.get_model('rental.RentalRequest')
    grace = max(int(params.get('grace_hours', 2)), 0)
    now = timezone.now()
    cutoff = now - timedelta(hours=grace)
    queryset = (
        RentalRequest.objects
        .filter(status='reserved', requested_start_date__lt=cutoff)
        .select_related('user')
        .order_by('requested_start_date')
    )
    return [
        Finding(
            obj=rental,
            dedup_key=f'rental.pickup_overdue|{rental.pk}',
            payload={
                'project_name': rental.project_name,
                'user': str(rental.user),
                'days_late': max((now - rental.requested_start_date).days, 0),
                'due_at': timezone.localtime(
                    rental.requested_start_date).isoformat(),
                'url': links.rental_detail_url(rental.pk),
            },
        )
        for rental in queryset
    ]


@scan_check('rental.return_overdue')
def check_return_overdue(params: Dict[str, int]) -> List[Finding]:
    """Find issued rentals that are late, escalating at a fixed interval."""
    RentalRequest = apps.get_model('rental.RentalRequest')
    grace = max(int(params.get('grace_days', 1)), 0)
    every = max(int(params.get('escalate_every', 7)), 1)
    now = timezone.now()
    cutoff = now - timedelta(days=grace)
    queryset = (
        RentalRequest.objects
        .filter(status='issued', requested_end_date__lt=cutoff)
        .select_related('user')
        .order_by('requested_end_date')
    )
    findings = []
    for rental in queryset:
        days_late = (now - rental.requested_end_date).days
        # A new bucket every `every` days, so the entry comes back after
        # being handled but is not repeated daily.
        bucket = days_late // every
        findings.append(Finding(
            obj=rental,
            dedup_key=f'rental.return_overdue|{rental.pk}|{bucket}',
            payload={
                'project_name': rental.project_name,
                'user': str(rental.user),
                'days_late': days_late,
                'url': links.rental_detail_url(rental.pk),
            },
        ))
    return findings


# ---------------------------------------------------------------------------
# licenses
# ---------------------------------------------------------------------------

@scan_check('licenses.unconfirmed_aging')
def check_unconfirmed_aging(params: Dict[str, int]) -> List[Finding]:
    """Find licenses that have been waiting for confirmation too long."""
    License = apps.get_model('licenses.License')
    now = timezone.now()
    cutoff = now - timedelta(days=params.get('days', 7))
    oldest = now - timedelta(days=max(
        int(params.get('lookback_days', 90)),
        int(params.get('days', 7)),
    ))
    queryset = (
        License.objects
        .filter(
            confirmed=False,
            created_at__lt=cutoff,
            created_at__gte=oldest,
        )
        .select_related('profile')
        .order_by('created_at')
    )
    findings = []
    for license_obj in queryset:
        findings.append(Finding(
            obj=license_obj,
            dedup_key=(
                f'licenses.unconfirmed_aging|{license_obj.pk}'
                f'|{timezone.localdate():%Y-%m}'
            ),
            payload={
                'number': license_obj.number,
                'title': license_obj.title,
                'created_at': license_obj.created_at.isoformat(),
                'url': _admin_url(license_obj),
            },
        ))
    return findings


@scan_check('licenses.nextcloud_download_pending')
def check_nextcloud_pending(params: Dict[str, int]) -> List[Finding]:
    """Find uploads that are still sitting in Nextcloud.

    The download task is started by hand from the license admin, so an
    upload stays invisible until somebody opens the list.
    """
    if not apps.is_installed('media_files'):
        # Without media_files there is no storage to download to.
        return []
    NextcloudVideoFile = apps.get_model('licenses.NextcloudVideoFile')
    queryset = (
        NextcloudVideoFile.objects
        .filter(
            user_uploaded=True,
            is_deleted=False,
            license__confirmed=True,
            license__is_live=False,
        )
        .select_related('license')
        .order_by('uploaded_at')
    )
    pending = list(queryset)
    numbers = [
        item.license.number for item in pending
        if item.license and item.license.number
    ]
    with_video = _numbers_with_video(numbers)

    findings = []
    for item in pending:
        license_obj = item.license
        if license_obj is None or license_obj.number in with_video:
            continue
        findings.append(Finding(
            obj=license_obj,
            dedup_key=f'licenses.nextcloud_download_pending|{item.pk}',
            payload={
                'number': license_obj.number,
                'filename': item.filename,
                'uploaded_at': (
                    item.uploaded_at.isoformat() if item.uploaded_at else ''),
                'url': _admin_url(license_obj),
            },
        ))
    return findings


@scan_check('licenses.confirmed_without_video')
def check_confirmed_without_video(params: Dict[str, int]) -> List[Finding]:
    """Find approved licenses still missing video after a quiet period."""
    if not apps.is_installed('media_files'):
        return []
    License = apps.get_model('licenses.License')
    now = timezone.now()
    cutoff = now - timedelta(days=params.get('days', 60))
    wait_cutoff = now - timedelta(days=max(
        int(params.get('wait_days', 3)), 0))
    queryset = (
        License.objects
        .filter(
            confirmed=True,
            confirmed_at__gte=cutoff,
            confirmed_at__lte=wait_cutoff,
            is_live=False,
        )
        .order_by('-confirmed_at')
    )
    licenses = list(queryset)
    with_video = _numbers_with_video(
        [item.number for item in licenses if item.number])
    NextcloudVideoFile = apps.get_model('licenses.NextcloudVideoFile')
    pending_upload_numbers = set(
        NextcloudVideoFile.objects.filter(
            license__in=licenses,
            user_uploaded=True,
            is_deleted=False,
        ).values_list('license__number', flat=True)
    )
    planned_numbers = set()
    if apps.is_installed('planung'):
        from planung.selectors import planned_entries

        horizon = max(int(config.get_params(
            'planung.plan_missing_video').get('horizon_days', 3)), 0)
        today = timezone.localdate()
        dates = [today + timedelta(days=offset)
                 for offset in range(horizon + 1)]
        planned_numbers = {
            entry['number'] for entry in planned_entries(dates)
            if entry['plan'].json_plan.get('planned') is True
            and entry['plan'].json_plan.get('draft') is not True
        }
    return [
        Finding(
            obj=license_obj,
            dedup_key=(
                f'licenses.confirmed_without_video|{license_obj.pk}'
                f'|{timezone.localdate():%Y-%m}'
            ),
            payload={
                'number': license_obj.number,
                'title': license_obj.title,
                'confirmed': True,
                'video_available': False,
                'url': _admin_url(license_obj),
            },
        )
        for license_obj in licenses
        if (license_obj.number not in with_video
            and license_obj.number not in pending_upload_numbers
            and license_obj.number not in planned_numbers)
    ]


# ---------------------------------------------------------------------------
# media_files
# ---------------------------------------------------------------------------

@scan_check('media_files.orphan_video')
def check_orphan_video(params: Dict[str, int]) -> List[Finding]:
    """Find recent video files that could not be linked to a license."""
    VideoFile = apps.get_model('media_files.VideoFile')
    storage_location_ids = params.get('storage_location_ids', [])
    if not storage_location_ids:
        return []
    cutoff = timezone.now() - timedelta(days=params.get('days', 30))
    grace_cutoff = timezone.now() - timedelta(hours=max(
        int(params.get('grace_hours', 24)), 0))
    queryset = (
        VideoFile.objects
        .filter(license__isnull=True, is_preview=False, is_available=True,
                created_at__gte=cutoff, created_at__lte=grace_cutoff,
                storage_location_id__in=storage_location_ids)
        .select_related('storage_location')
        .order_by('-created_at')
    )
    return [
        Finding(
            obj=video,
            dedup_key=f'media_files.orphan_video|{video.pk}',
            payload={
                'filename': video.filename,
                'number': video.number,
                'storage': str(video.storage_location or ''),
                'url': _admin_url(video),
            },
        )
        for video in queryset
    ]


@scan_check('media_files.storage_low')
def check_storage_low(params: Dict[str, int]) -> List[Finding]:
    """Find storage locations that are running out of free space."""
    StorageLocation = apps.get_model('media_files.StorageLocation')
    threshold = max(int(params.get('threshold_percent', 10)), 0)
    findings = []
    for storage in StorageLocation.objects.filter(is_active=True):
        if not storage.path:
            continue
        try:
            usage = shutil.disk_usage(storage.path)
        except OSError:
            # A path that is not mounted right now is a different problem.
            logger.warning('Could not read disk usage for %s', storage.path)
            continue
        if not usage.total:
            continue
        free_percent = round(usage.free * 100 / usage.total, 1)
        if free_percent >= threshold:
            continue
        findings.append(Finding(
            obj=storage,
            dedup_key=(
                f'media_files.storage_low|{storage.pk}'
                f'|{timezone.localdate():%Y-%m-%d}'
            ),
            payload={
                'name': storage.name,
                'free_percent': free_percent,
                'free_gb': round(usage.free / 1024 ** 3, 1),
                'url': _admin_url(storage),
            },
        ))
    return findings


@scan_check('media_files.storage_unavailable')
def check_storage_unavailable(params: Dict[str, int]) -> List[Finding]:
    """Find active storage locations whose paths cannot be read."""
    StorageLocation = apps.get_model('media_files.StorageLocation')
    findings = []
    for storage in StorageLocation.objects.filter(is_active=True):
        if not storage.path:
            continue
        try:
            shutil.disk_usage(storage.path)
        except OSError as error:
            findings.append(Finding(
                obj=storage,
                dedup_key=f'media_files.storage_unavailable|{storage.pk}',
                payload={
                    'name': storage.name,
                    'path': storage.path,
                    'error': str(error)[:200],
                    'url': _admin_url(storage),
                },
            ))
    return findings


@scan_check('media_files.format_mismatch')
def check_format_mismatch(params: Dict[str, int]) -> List[Finding]:
    """Find recent videos whose format differs from the encoding preset."""
    from media_files.utils import format_deviation
    from media_files.utils import get_target_encode_preset

    preset = get_target_encode_preset()
    if preset is None:
        # Without a preset there is no norm to compare against.
        return []

    VideoFile = apps.get_model('media_files.VideoFile')
    cutoff = timezone.now() - timedelta(days=params.get('days', 30))
    queryset = (
        VideoFile.objects
        .filter(
            license__isnull=False,
            is_preview=False,
            is_available=True,
            created_at__gte=cutoff,
        )
        .exclude(width__isnull=True)
        .select_related('storage_location')
        .order_by('-created_at')
    )
    findings = []
    for video in queryset:
        deviation = format_deviation(video, preset)
        if not deviation:
            continue
        parts = [
            f'{key} {value["actual"]} != {value["expected"]}'
            for key, value in sorted(deviation.items())
        ]
        findings.append(Finding(
            obj=video,
            dedup_key=f'media_files.format_mismatch|{video.pk}',
            payload={
                'filename': video.filename,
                'number': video.number,
                'deviation': ', '.join(parts),
                'url': _admin_url(video),
            },
        ))
    return findings


def _own_planned_entries(horizon_days: int):
    """Return planned entries of own productions within the horizon.

    Shared by the reel and the cover check: same selection, different
    question about the result.
    """
    from notifications.org import own_license_numbers
    from planung import selectors as planung_selectors

    if not apps.is_installed('planung'):
        return [], None
    horizon = max(int(horizon_days), 0)
    today = timezone.localdate()
    dates = [today + timedelta(days=offset)
             for offset in range(0, horizon + 1)]
    entries = [
        entry for entry in planung_selectors.planned_entries(dates)
        if entry['plan'].json_plan.get('planned') is True
        and entry['plan'].json_plan.get('draft') is not True
    ]
    if not entries:
        return [], set()

    own = own_license_numbers({entry['number'] for entry in entries})
    if own is None:
        # The own media authority is not configured yet; answering would
        # mean reporting other channels' material as ours.
        return [], None
    License = apps.get_model('licenses.License')
    confirmed = set(
        License.objects.filter(
            number__in=own, confirmed=True, is_live=False)
        .values_list('number', flat=True))
    eligible = confirmed & _numbers_with_video(confirmed)
    return [
        entry for entry in entries if entry['number'] in eligible
    ], eligible


def _missing_asset_findings(code: str, entries, have_numbers) -> List[Finding]:
    """Build findings for planned own productions missing an asset."""
    License = apps.get_model('licenses.License')
    licenses = {
        license_obj.number: license_obj
        for license_obj in License.objects.filter(
            number__in={entry['number'] for entry in entries})
    }
    findings = []
    for entry in entries:
        if entry['number'] in have_numbers:
            continue
        payload = {
            'date': entry['date'].strftime('%d.%m.%Y'),
            'number': entry['number'],
            'title': entry['title'],
            'start': entry['start'],
            'confirmed': True,
            'video_available': True,
            'url': links.planung_calendar_url(entry['date']),
        }
        if code == 'media_files.missing_reel':
            payload['reel_available'] = False
        else:
            payload['cover_available'] = False
        findings.append(Finding(
            obj=licenses.get(entry['number']),
            dedup_key=f'{code}|{entry["date"]:%Y-%m-%d}|{entry["number"]}',
            payload=payload,
        ))
    return findings


def _reel_relevant_numbers(numbers):
    """Restrict reel work to material a reel would actually promote.

    A reel advertises something the audience can watch: a premiere (the licence
    has no contribution yet), or a repeat that is available in the Mediathek.
    A repeat without a Mediathek link has nothing to link to, so asking for a
    reel would only produce noise.
    """
    License = apps.get_model('licenses.License')
    Contribution = apps.get_model('contributions.Contribution')

    numbers = set(numbers)
    if not numbers:
        return numbers
    repeated = set(
        Contribution.objects.filter(license__number__in=numbers)
        .values_list('license__number', flat=True)
    )
    premieres = numbers - repeated
    in_mediathek = set(
        License.objects.filter(number__in=repeated)
        .exclude(mediathek_url='')
        .exclude(mediathek_url__isnull=True)
        .values_list('number', flat=True)
    )
    return premieres | in_mediathek


@scan_check('media_files.missing_reel')
def check_missing_reel(params: Dict[str, int]) -> List[Finding]:
    """Find own productions going on air soon without a rendered reel."""
    from media_files.utils import numbers_with_reel

    entries, own = _own_planned_entries(params.get('horizon_days', 3))
    if own is None or not entries:
        return []
    relevant = _reel_relevant_numbers({entry['number'] for entry in entries})
    entries = [entry for entry in entries if entry['number'] in relevant]
    if not entries:
        return []
    return _missing_asset_findings(
        'media_files.missing_reel', entries,
        numbers_with_reel({entry['number'] for entry in entries}))


@scan_check('media_files.missing_cover')
def check_missing_cover(params: Dict[str, int]) -> List[Finding]:
    """Find premieres of own productions going on air without a cover."""
    from media_files.utils import numbers_with_cover

    entries, own = _own_planned_entries(params.get('horizon_days', 3))
    if own is None or not entries:
        return []
    Contribution = apps.get_model('contributions.Contribution')
    repeated_numbers = set(
        Contribution.objects.filter(license__number__in=own)
        .values_list('license__number', flat=True)
    )
    premiere_entries = [
        entry for entry in entries
        if entry['number'] not in repeated_numbers
    ]
    return _missing_asset_findings(
        'media_files.missing_cover', premiere_entries,
        numbers_with_cover({entry['number'] for entry in premiere_entries}))


@scan_check('media_files.reel_post_today')
def check_reel_post_today(params: Dict[str, int]) -> List[Finding]:
    """Find ready reels that somebody has to publish on the air date."""
    from media_files.utils import numbers_with_reel

    entries, own = _own_planned_entries(0)
    if own is None or not entries:
        return []
    relevant = _reel_relevant_numbers({entry['number'] for entry in entries})
    entries = [entry for entry in entries if entry['number'] in relevant]
    if not entries:
        return []
    reel_numbers = numbers_with_reel(
        {entry['number'] for entry in entries})
    License = apps.get_model('licenses.License')
    licenses = {
        item.number: item for item in License.objects.filter(
            number__in=reel_numbers)
    }
    return [
        Finding(
            obj=licenses.get(entry['number']),
            dedup_key=(
                f'media_files.reel_post_today|{entry["date"]:%Y-%m-%d}'
                f'|{entry["number"]}'),
            payload={
                'date': entry['date'].strftime('%d.%m.%Y'),
                'number': entry['number'],
                'title': entry['title'],
                'start': entry['start'],
                'reel_available': True,
                'url': links.planung_calendar_url(entry['date']),
            },
        )
        for entry in entries if entry['number'] in reel_numbers
    ]


# ---------------------------------------------------------------------------
# reminders
# ---------------------------------------------------------------------------


@scan_check('reminders.manual')
def check_manual_reminders(params: Dict[str, int]) -> List[Finding]:
    """Return the staff written reminders that are due today.

    One finding per reminder and day, so a weekly reminder reappears every
    week instead of being deduplicated away after the first time.
    """
    ManualReminder = apps.get_model('notifications.ManualReminder')

    today = timezone.localdate()
    findings = []
    for reminder in ManualReminder.objects.filter(active=True):
        if not reminder.is_due(today):
            continue
        findings.append(Finding(
            obj=reminder,
            dedup_key=f'reminders.manual|{reminder.pk}|{today:%Y-%m-%d}',
            payload={
                'title': reminder.title,
                'message': reminder.message,
                'schedule': str(reminder.schedule_label()),
                'date': today.strftime('%d.%m.%Y'),
                'url': reminder.url,
            },
        ))
    return findings


# ---------------------------------------------------------------------------
# austausch
# ---------------------------------------------------------------------------

@scan_check('austausch.new_items')
def check_exchange_new_items(params: Dict[str, int]) -> List[Finding]:
    """Find exchange material that was discovered but never imported."""
    ExchangeItem = apps.get_model('austausch.ExchangeItem')
    cutoff = timezone.now() - timedelta(days=params.get('days', 14))
    queryset = (
        ExchangeItem.objects
        .filter(import_status='new', discovered_at__gte=cutoff)
        .order_by('-discovered_at')
    )
    return [
        Finding(
            obj=item,
            dedup_key=f'austausch.new_items|{item.pk}',
            payload={
                'title': item.title or item.filename,
                'channel': item.channel,
                'discovered_at': (
                    item.discovered_at.isoformat()
                    if item.discovered_at else ''),
                'url': links.exchange_feed_url(
                    search=item.filename, status='new'),
            },
        )
        for item in queryset
    ]


# ---------------------------------------------------------------------------
# planung
# ---------------------------------------------------------------------------

@scan_check('planung.plan_missing')
def check_plan_missing(params: Dict[str, int]) -> List[Finding]:
    """Find the coming days that have no plan, or an empty one."""
    from planung import selectors as planung_selectors

    horizon = max(int(params.get('horizon_days', 2)), 1)
    today = timezone.localdate()
    dates = [today + timedelta(days=offset)
             for offset in range(1, horizon + 1)]
    plans = planung_selectors.plans_for(dates)
    findings = []
    for day in dates:
        plan = plans.get(day)
        if (plan is not None
                and plan.json_plan.get('planned') is True
                and plan.json_plan.get('draft') is not True
                and planung_selectors.plan_items(plan)):
            continue
        findings.append(Finding(
            obj=plan,
            dedup_key=f'planung.plan_missing|{day:%Y-%m-%d}',
            payload={
                'date': day.strftime('%d.%m.%Y'),
                'url': links.planung_calendar_url(day),
            },
        ))
    return findings


@scan_check('planung.plan_missing_video')
def check_plan_missing_video(params: Dict[str, int]) -> List[Finding]:
    """Find planned entries whose license has no available video file."""
    from planung import selectors as planung_selectors

    horizon = max(int(params.get('horizon_days', 3)), 0)
    today = timezone.localdate()
    dates = [today + timedelta(days=offset)
             for offset in range(0, horizon + 1)]
    entries = [
        entry for entry in planung_selectors.planned_entries(dates)
        if entry['plan'].json_plan.get('planned') is True
        and entry['plan'].json_plan.get('draft') is not True
    ]
    License = apps.get_model('licenses.License')
    live_numbers = set(
        License.objects.filter(
            number__in={entry['number'] for entry in entries}, is_live=True)
        .values_list('number', flat=True))
    with_video = _numbers_with_video(
        {entry['number'] for entry in entries})

    findings = []
    for entry in entries:
        if entry['number'] in live_numbers or entry['number'] in with_video:
            continue
        findings.append(Finding(
            obj=entry['plan'],
            dedup_key=(
                f'planung.plan_missing_video|{entry["date"]:%Y-%m-%d}'
                f'|{entry["number"]}'),
            payload={
                'date': entry['date'].strftime('%d.%m.%Y'),
                'start': entry['start'],
                'number': entry['number'],
                'title': entry['title'],
                'url': links.planung_calendar_url(entry['date']),
            },
        ))
    return findings


@scan_check('planung.live_today')
def check_live_today(params: Dict[str, int]) -> List[Finding]:
    """Show committed live contributions in today's expectations."""
    from planung import selectors as planung_selectors

    today = timezone.localdate()
    entries = [
        entry for entry in planung_selectors.planned_entries([today])
        if entry['plan'].json_plan.get('planned') is True
        and entry['plan'].json_plan.get('draft') is not True
    ]
    License = apps.get_model('licenses.License')
    live_licenses = {
        license_obj.number: license_obj
        for license_obj in License.objects.filter(
            number__in={entry['number'] for entry in entries}, is_live=True)
    }
    return [
        Finding(
            obj=live_licenses[entry['number']],
            payload={
                'date': today.strftime('%d.%m.%Y'),
                'start': entry['start'],
                'number': entry['number'],
                'title': entry['title'],
                'live': True,
                'url': links.planung_calendar_url(today),
            },
        )
        for entry in entries if entry['number'] in live_licenses
    ]


@scan_check('planung.not_aired')
def check_not_aired(params: Dict[str, int]) -> List[Finding]:
    """Find scheduled entries whose broadcast never started."""
    AirReport = apps.get_model('planung.AirReport')
    now = timezone.now()
    cutoff = now - timedelta(days=params.get('days', 3))
    due_before = now - timedelta(minutes=max(
        int(params.get('grace_minutes', 5)), 0))
    queryset = (
        AirReport.objects
        .filter(started_at__isnull=True, scheduled_start__lt=due_before,
                scheduled_start__gte=cutoff)
        .order_by('-scheduled_start')
    )
    return [
        Finding(
            obj=report,
            dedup_key=f'planung.not_aired|{report.pk}',
            payload={
                'scheduled_at': timezone.localtime(
                    report.scheduled_start).strftime('%d.%m.%Y %H:%M'),
                'filename': report.media_filename,
                'url': links.planung_calendar_url(
                    timezone.localtime(report.scheduled_start).date()),
            },
        )
        for report in queryset
    ]


# ---------------------------------------------------------------------------
# system
# ---------------------------------------------------------------------------

@scan_check('system.task_failures')
def check_task_failures(params: Dict[str, int]) -> List[Finding]:
    """Count failed background tasks, grouped by task name.

    One entry per task name instead of per failure: a broken task fails on
    every run and would otherwise fill the whole page.
    """
    if not apps.is_installed('django_celery_results'):
        return []
    TaskResult = apps.get_model('django_celery_results.TaskResult')
    cutoff = timezone.now() - timedelta(hours=params.get('hours', 24))
    rows = (
        TaskResult.objects
        .filter(status='FAILURE', date_done__gte=cutoff)
        .values('task_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    return [
        Finding(
            dedup_key=(
                f'system.task_failures|{row["task_name"]}'
                f'|{timezone.localdate():%Y-%m-%d}'
            ),
            payload={
                'task': row['task_name'] or '?',
                'count': row['count'],
            },
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

@scan_check('registration.unverified_aging')
def check_unverified_aging(params: Dict[str, int]) -> List[Finding]:
    """Find profiles that have been waiting for verification too long."""
    Profile = apps.get_model('registration.Profile')
    now = timezone.now()
    cutoff = now - timedelta(days=params.get('days', 14))
    oldest = now - timedelta(days=max(
        int(params.get('lookback_days', 90)),
        int(params.get('days', 14)),
    ))
    queryset = (
        Profile.objects
        .filter(
            verified=False,
            created_at__lt=cutoff,
            created_at__gte=oldest,
        )
        .select_related('okuser')
        .order_by('created_at')
    )
    return [
        Finding(
            obj=profile,
            dedup_key=(
                f'registration.unverified_aging|{profile.pk}'
                f'|{timezone.localdate():%Y-%m}'
            ),
            payload={
                'name': f'{profile.first_name} {profile.last_name}'.strip(),
                'email': getattr(profile.okuser, 'email', ''),
                'url': _admin_url(profile),
            },
        )
        for profile in queryset
    ]
