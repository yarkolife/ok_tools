"""Signal based event sources.

Handlers are attached lazily so that a deployment without the owning app
still imports cleanly. Events are always emitted after commit: a rollback
must never leave a notification about an object that does not exist.
"""

from django.apps import apps
from django.db.models.signals import post_save
from notifications import links
from notifications.services import emit_on_commit
from notifications.utils import admin_url
import logging


logger = logging.getLogger('django')


def on_license_created(sender, instance, created, **kwargs):
    """Report a freshly created license that still needs confirmation."""
    if not created or getattr(instance, 'confirmed', False):
        return
    emit_on_commit(
        'licenses.new_unconfirmed',
        obj=instance,
        payload={
            'number': instance.number,
            'title': instance.title,
            'url': admin_url(instance),
        },
    )


def on_video_file_created(sender, instance, created, **kwargs):
    """Report a video the storage scan picked up.

    Preview clips are the rendered reels; they are produced by the system
    itself and need no review.
    """
    if not created or getattr(instance, 'is_preview', False):
        return
    storage = getattr(instance, 'storage_location', None)
    emit_on_commit(
        'media_files.new_video',
        obj=instance,
        payload={
            'filename': instance.filename,
            'number': instance.number,
            'storage': str(storage) if storage else '',
            'url': admin_url(instance),
        },
    )


def on_profile_created(sender, instance, created, **kwargs):
    """Report a new registration that still has to be verified."""
    if not created or getattr(instance, 'verified', False):
        return
    emit_on_commit(
        'registration.new_profile',
        obj=instance,
        payload={
            'name': f'{instance.first_name} {instance.last_name}'.strip(),
            'email': getattr(instance.okuser, 'email', ''),
            'url': admin_url(instance),
        },
    )


def on_rental_issue_created(sender, instance, created, **kwargs):
    """Report damage or a defect somebody recorded on a rental."""
    if not created or getattr(instance, 'resolved', False):
        return
    rental_item = getattr(instance, 'rental_item', None)
    rental_id = getattr(rental_item, 'rental_request_id', None)
    emit_on_commit(
        'rental.issue_reported',
        obj=instance,
        payload={
            'item': str(instance.rental_item),
            'issue': instance.get_issue_type_display(),
            'severity': instance.get_severity_display(),
            'url': links.rental_detail_url(rental_id),
        },
    )


def on_file_operation_saved(sender, instance, created, **kwargs):
    """Report a render, transcode or copy job that ended with an error."""
    if str(instance.status).lower() != 'failed':
        return
    video = getattr(instance, 'video_file', None)
    emit_on_commit(
        'media_files.operation_failed',
        obj=video,
        dedup_key=f'media_files.operation_failed|{instance.pk}',
        payload={
            'operation': instance.get_operation_type_display(),
            'filename': getattr(video, 'filename', ''),
            'error': (instance.error_message or '')[:200],
            'url': admin_url(video),
        },
    )


def on_exchange_import_saved(sender, instance, created, **kwargs):
    """Report an exchange download or import that did not work."""
    if instance.status != 'failed':
        return
    item = getattr(instance, 'exchange_item', None)
    emit_on_commit(
        'austausch.import_failed',
        obj=item,
        dedup_key=f'austausch.import_failed|{instance.pk}',
        payload={
            'filename': getattr(item, 'filename', ''),
            'error': (instance.error_message or '')[:200],
            'url': links.exchange_feed_url(
                search=getattr(item, 'filename', '')),
        },
    )


def _emit_job_finished(instance, label: str, owner_field: str) -> None:
    """Report a finished job to whoever started it."""
    if instance.status not in ('completed', 'failed'):
        return
    owner = getattr(instance, owner_field, None)
    if owner is None:
        return
    emit_on_commit(
        'tools.job_finished',
        obj=instance,
        dedup_key=(
            f'tools.job_finished|{instance._meta.model_name}'
            f'|{instance.pk}|{instance.status}'
        ),
        payload={
            'job': f'{label}: {instance}',
            'status': instance.get_status_display(),
            'url': admin_url(instance),
        },
        recipients=[owner],
    )


def on_slideshow_saved(sender, instance, created, **kwargs):
    """Report a finished slideshow render."""
    _emit_job_finished(instance, 'Slideshow', 'created_by')


def on_audio_job_saved(sender, instance, created, **kwargs):
    """Report a finished audio normalisation job."""
    _emit_job_finished(instance, 'Audio', 'created_by')


def connect_handlers() -> None:
    """Attach the handlers of the apps that are installed."""
    if apps.is_installed('licenses'):
        post_save.connect(
            on_license_created,
            sender=apps.get_model('licenses.License'),
            dispatch_uid='notifications.licenses.new_unconfirmed',
        )
    if apps.is_installed('media_files'):
        post_save.connect(
            on_video_file_created,
            sender=apps.get_model('media_files.VideoFile'),
            dispatch_uid='notifications.media_files.new_video',
        )
        post_save.connect(
            on_file_operation_saved,
            sender=apps.get_model('media_files.FileOperation'),
            dispatch_uid='notifications.media_files.operation_failed',
        )
    if apps.is_installed('rental'):
        post_save.connect(
            on_rental_issue_created,
            sender=apps.get_model('rental.RentalIssue'),
            dispatch_uid='notifications.rental.issue_reported',
        )
    if apps.is_installed('austausch'):
        post_save.connect(
            on_exchange_import_saved,
            sender=apps.get_model('austausch.ExchangeImport'),
            dispatch_uid='notifications.austausch.import_failed',
        )
    if apps.is_installed('tools'):
        post_save.connect(
            on_slideshow_saved,
            sender=apps.get_model('tools.SlideshowProject'),
            dispatch_uid='notifications.tools.slideshow_finished',
        )
        post_save.connect(
            on_audio_job_saved,
            sender=apps.get_model('tools.AudioNormalizeJob'),
            dispatch_uid='notifications.tools.audio_finished',
        )
    post_save.connect(
        on_profile_created,
        sender=apps.get_model('registration.Profile'),
        dispatch_uid='notifications.registration.new_profile',
    )


connect_handlers()
