"""Declarations of the event types this installation knows about.

The catalogue is the one agreed in ``plans/notifications-digest-plan.md``.
Adding a type here needs no migration: the configuration rows are
synchronised from this registry after ``migrate``.
"""

from django.utils.translation import gettext_lazy as _
from notifications.registry import CATEGORY_ACTION_REQUIRED
from notifications.registry import CATEGORY_INFO
from notifications.registry import CATEGORY_PROBLEM
from notifications.registry import SOURCE_SCAN
from notifications.registry import SOURCE_SIGNAL
from notifications.registry import EventType
from notifications.registry import ParamSpec
from notifications.registry import register


# ---------------------------------------------------------------------------
# rental
# ---------------------------------------------------------------------------

# Expectation: recomputed on every render, never stored. A rental moved to
# another day has to disappear without leaving a row behind.
RENTAL_PICKUP_DUE = register(EventType(
    code='rental.pickup_due_today',
    module='rental',
    label=_('Equipment to hand out'),
    description=_('Reserved equipment whose pick-up date is reached.'),
    message=_('{project_name} ({user})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    expectation=True,
    model='rental.RentalRequest',
    settings_flag='RENTAL_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days ahead'),
            default=0,
            help_text=_('0 shows today only, 1 also shows tomorrow.'),
        ),
    ),
))

RENTAL_RETURN_DUE = register(EventType(
    code='rental.return_due_today',
    module='rental',
    label=_('Equipment due back'),
    description=_('Issued equipment whose return date is reached.'),
    message=_('{project_name} ({user})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    expectation=True,
    model='rental.RentalRequest',
    settings_flag='RENTAL_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days ahead'),
            default=0,
            help_text=_('0 shows today only, 1 also shows tomorrow.'),
        ),
    ),
))

# Stored, so that the escalation steps stay visible in the feed.
RENTAL_OVERDUE = register(EventType(
    code='rental.return_overdue',
    module='rental',
    label=_('Equipment overdue'),
    description=_('Issued equipment that was not returned in time.'),
    message=_('{project_name} ({user}), {days_late} days late'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='rental.RentalRequest',
    settings_flag='RENTAL_ENABLED',
    params=(
        ParamSpec(
            name='grace_days',
            label=_('Grace period (days)'),
            default=1,
            help_text=_('Report only after the return is this many days late.'),
        ),
        ParamSpec(
            name='escalate_every',
            label=_('Repeat every (days)'),
            default=7,
            help_text=_('Raise the entry again after this many days.'),
        ),
    ),
))


RENTAL_ISSUE_REPORTED = register(EventType(
    code='rental.issue_reported',
    module='rental',
    label=_('Problem reported with rented equipment'),
    description=_('Somebody recorded damage or a defect on a rental.'),
    message=_('{item}: {issue} ({severity})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SIGNAL,
    model='rental.RentalIssue',
    settings_flag='RENTAL_ENABLED',
))


# ---------------------------------------------------------------------------
# licenses
# ---------------------------------------------------------------------------

LICENSE_NEW_UNCONFIRMED = register(EventType(
    code='licenses.new_unconfirmed',
    module='licenses',
    label=_('New license waiting for confirmation'),
    description=_('A license was created and still needs to be confirmed.'),
    message=_('License {number}: {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SIGNAL,
    model='licenses.License',
    settings_flag='LICENSES_ENABLED',
))

LICENSE_UNCONFIRMED_AGING = register(EventType(
    code='licenses.unconfirmed_aging',
    module='licenses',
    label=_('License unconfirmed for too long'),
    description=_('The license has been waiting for confirmation for a while.'),
    message=_('License {number}: {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='licenses.License',
    settings_flag='LICENSES_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Days to wait'),
            default=7,
            help_text=_('Report a license once it has waited this many days.'),
        ),
    ),
))

# The download task is only ever started by hand from the license admin, so
# without this nobody learns that an author uploaded something.
LICENSE_NEXTCLOUD_PENDING = register(EventType(
    code='licenses.nextcloud_download_pending',
    module='licenses',
    label=_('Uploaded video waiting to be downloaded'),
    description=_(
        'An author uploaded a video to Nextcloud and it is not on a storage '
        'location yet.'),
    message=_('License {number}: {filename}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='licenses.License',
    settings_flag='LICENSES_ENABLED',
))


LICENSE_CONFIRMED_WITHOUT_VIDEO = register(EventType(
    code='licenses.confirmed_without_video',
    module='licenses',
    label=_('Confirmed license without a video file'),
    description=_(
        'The license is approved but has no video, so it cannot be planned.'),
    message=_('License {number}: {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='licenses.License',
    settings_flag='LICENSES_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Confirmed within (days)'),
            default=60,
            help_text=_('Only look at licenses confirmed recently.'),
        ),
    ),
))


# ---------------------------------------------------------------------------
# media_files
# ---------------------------------------------------------------------------

MEDIA_NEW_VIDEO = register(EventType(
    code='media_files.new_video',
    module='media_files',
    label=_('New video found'),
    description=_('The storage scan picked up a video that nobody checked.'),
    message=_('{filename} ({storage})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SIGNAL,
    model='media_files.VideoFile',
    settings_flag='MEDIA_FILES_ENABLED',
))

# The norm is the configured encoding preset, never a hard-coded number.
MEDIA_FORMAT_MISMATCH = register(EventType(
    code='media_files.format_mismatch',
    module='media_files',
    label=_('Video format has to be converted'),
    description=_(
        'Resolution or frame rate differ from the configured encoding '
        'preset, so the file has to be transcoded.'),
    message=_('{filename}: {deviation}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='media_files.VideoFile',
    settings_flag='MEDIA_FILES_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Added within (days)'),
            default=30,
            help_text=_('Only check files that appeared recently.'),
        ),
    ),
))

# Reel and cover are two separate types on purpose: a channel may produce
# covers but no reels, and one combined type could not be switched off
# halfway.
MEDIA_MISSING_REEL = register(EventType(
    code='media_files.missing_reel',
    module='media_files',
    label=_('Planned own production without a reel'),
    description=_(
        'An own production is scheduled soon and no reel was rendered yet.'),
    message=_('{date}: {number} {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='licenses.License',
    settings_flag='MEDIA_FILES_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days before broadcast'),
            default=3,
            help_text=_('Warn this many days before the broadcast date.'),
        ),
    ),
))

MEDIA_MISSING_COVER = register(EventType(
    code='media_files.missing_cover',
    module='media_files',
    label=_('Planned own production without a cover'),
    description=_(
        'An own production is scheduled soon and no cover image exists.'),
    message=_('{date}: {number} {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='licenses.License',
    settings_flag='MEDIA_FILES_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days before broadcast'),
            default=3,
            help_text=_('Warn this many days before the broadcast date.'),
        ),
    ),
))


MEDIA_ORPHAN_VIDEO = register(EventType(
    code='media_files.orphan_video',
    module='media_files',
    label=_('Video without a license'),
    description=_('A video file could not be linked to any license.'),
    message=_('{filename} ({storage})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='media_files.VideoFile',
    settings_flag='MEDIA_FILES_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Added within (days)'),
            default=30,
            help_text=_('Only report files that appeared recently.'),
        ),
    ),
))

MEDIA_OPERATION_FAILED = register(EventType(
    code='media_files.operation_failed',
    module='media_files',
    label=_('File operation failed'),
    description=_('A render, transcode or copy job ended with an error.'),
    message=_('{operation}: {filename}'),
    category=CATEGORY_PROBLEM,
    source=SOURCE_SIGNAL,
    model='media_files.VideoFile',
    settings_flag='MEDIA_FILES_ENABLED',
))

MEDIA_STORAGE_LOW = register(EventType(
    code='media_files.storage_low',
    module='media_files',
    label=_('Storage is running out of space'),
    description=_('A storage location has little free space left.'),
    message=_('{name}: {free_percent}% free ({free_gb} GB)'),
    category=CATEGORY_PROBLEM,
    source=SOURCE_SCAN,
    model='media_files.StorageLocation',
    settings_flag='MEDIA_FILES_ENABLED',
    params=(
        ParamSpec(
            name='threshold_percent',
            label=_('Warn below (%)'),
            default=10,
            help_text=_('Report when less than this share of space is free.'),
        ),
    ),
))


# ---------------------------------------------------------------------------
# austausch
# ---------------------------------------------------------------------------

EXCHANGE_IMPORT_FAILED = register(EventType(
    code='austausch.import_failed',
    module='austausch',
    label=_('Exchange import failed'),
    description=_('Downloading or importing exchange material did not work.'),
    message=_('{filename}: {error}'),
    category=CATEGORY_PROBLEM,
    source=SOURCE_SIGNAL,
    model='austausch.ExchangeItem',
    settings_flag='AUSTAUSCH_ENABLED',
))

EXCHANGE_NEW_ITEMS = register(EventType(
    code='austausch.new_items',
    module='austausch',
    label=_('New material in the exchange'),
    description=_('The exchange folder scan found material not imported yet.'),
    message=_('{title} ({channel})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='austausch.ExchangeItem',
    settings_flag='AUSTAUSCH_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Discovered within (days)'),
            default=14,
            help_text=_('Ignore material discovered longer ago than this.'),
        ),
    ),
))


# ---------------------------------------------------------------------------
# planung
# ---------------------------------------------------------------------------

# The most expensive event in the catalogue: a missing plan is dead air.
PLAN_MISSING = register(EventType(
    code='planung.plan_missing',
    module='planung',
    label=_('No broadcast plan'),
    description=_('There is no plan for one of the next days, or it is empty.'),
    message=_('{date}'),
    # Editorial work, not a technical fault: it belongs in the counter.
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='planung.TagesPlan',
    settings_flag='PLANUNG_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days ahead'),
            default=2,
            help_text=_('How many days ahead the plan has to exist.'),
        ),
    ),
))

PLAN_MISSING_VIDEO = register(EventType(
    code='planung.plan_missing_video',
    module='planung',
    label=_('Planned entry without a video file'),
    description=_('A number in the plan has no available video file.'),
    message=_('{date}, {start}: {number} {title}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SCAN,
    model='planung.TagesPlan',
    settings_flag='PLANUNG_ENABLED',
    params=(
        ParamSpec(
            name='horizon_days',
            label=_('Days ahead'),
            default=3,
            help_text=_('How far ahead the plan is checked for missing media.'),
        ),
    ),
))


PLAN_NOT_AIRED = register(EventType(
    code='planung.not_aired',
    module='planung',
    label=_('Scheduled entry did not go on air'),
    description=_(
        'The playout reported a scheduled start that never actually began.'),
    message=_('{scheduled_at}: {filename}'),
    category=CATEGORY_PROBLEM,
    source=SOURCE_SCAN,
    model='planung.AirReport',
    settings_flag='PLANUNG_ENABLED',
    params=(
        ParamSpec(
            name='days',
            label=_('Look back (days)'),
            default=3,
            help_text=_('How far back missed broadcasts are reported.'),
        ),
    ),
))


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------

# Addressed to whoever started the job, not to the module subscribers.
TOOLS_JOB_FINISHED = register(EventType(
    code='tools.job_finished',
    module='tools',
    label=_('Render job finished'),
    description=_('A slideshow or audio job you started has ended.'),
    message=_('{job}: {status}'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SIGNAL,
    settings_flag='TOOLS_ENABLED',
))


# ---------------------------------------------------------------------------
# system
# ---------------------------------------------------------------------------

SYSTEM_TASK_FAILURES = register(EventType(
    code='system.task_failures',
    module='system',
    label=_('Background tasks are failing'),
    description=_(
        'Celery recorded failed tasks, for example a database backup that '
        'did not run.'),
    message=_('{task}: {count} failures'),
    category=CATEGORY_PROBLEM,
    source=SOURCE_SCAN,
    superuser_only=True,
    params=(
        ParamSpec(
            name='hours',
            label=_('Look back (hours)'),
            default=24,
            help_text=_('How far back failed tasks are counted.'),
        ),
    ),
))


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------

REGISTRATION_NEW_PROFILE = register(EventType(
    code='registration.new_profile',
    module='registration',
    label=_('New registration waiting for verification'),
    description=_('Somebody registered and the profile is not verified yet.'),
    message=_('{name} ({email})'),
    category=CATEGORY_ACTION_REQUIRED,
    source=SOURCE_SIGNAL,
    model='registration.Profile',
))

REGISTRATION_UNVERIFIED_AGING = register(EventType(
    code='registration.unverified_aging',
    module='registration',
    label=_('Profile unverified for too long'),
    description=_('The profile has been waiting for verification for a while.'),
    message=_('{name} ({email})'),
    category=CATEGORY_INFO,
    source=SOURCE_SCAN,
    model='registration.Profile',
    params=(
        ParamSpec(
            name='days',
            label=_('Days to wait'),
            default=14,
            help_text=_('Report a profile once it has waited this many days.'),
        ),
    ),
))
