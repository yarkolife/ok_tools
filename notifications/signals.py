"""Signal based event sources.

Handlers are attached lazily so that a deployment without the owning app
still imports cleanly. Events are always emitted after commit: a rollback
must never leave a notification about an object that does not exist.
"""

from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_save
from notifications import links
from notifications.process_state import refresh_missing_asset_events
from notifications.services import emit
from notifications.services import emit_on_commit
from notifications.utils import admin_url
import logging


logger = logging.getLogger('django')


def _advance_confirmed_license(license_id: int) -> None:
    """Evaluate the next steps after confirmation has committed."""
    NextcloudVideoFile = apps.get_model('licenses.NextcloudVideoFile')
    for upload_id in NextcloudVideoFile.objects.filter(
            license_id=license_id,
            user_uploaded=True,
            is_deleted=False).values_list('pk', flat=True):
        _emit_nextcloud_pending(upload_id)
    refresh_missing_asset_events()


def on_license_saved(sender, instance, created, **kwargs):
    """Report the currently blocking step of the license workflow."""
    cache.delete('notifications:expectation:planung.live_today')
    if created and not getattr(instance, 'confirmed', False):
        emit_on_commit(
            'licenses.new_unconfirmed',
            obj=instance,
            payload={
                'number': instance.number,
                'title': instance.title,
                'confirmed': False,
                'url': admin_url(instance),
            },
        )
    if getattr(instance, 'confirmed', False):
        transaction.on_commit(
            lambda: _advance_confirmed_license(instance.pk))


def on_video_file_created(sender, instance, created, **kwargs):
    """Re-evaluate attention items after automatic media processing."""
    if not created:
        return
    cache.delete('notifications:expectation:planung.live_today')
    transaction.on_commit(refresh_missing_asset_events)


def _emit_nextcloud_pending(upload_id: int) -> None:
    """Raise a manual download task only after the upload is complete."""
    if not apps.is_installed('media_files'):
        return
    NextcloudVideoFile = apps.get_model('licenses.NextcloudVideoFile')
    upload = (
        NextcloudVideoFile.objects
        .select_related('license')
        .filter(
            pk=upload_id,
            user_uploaded=True,
            is_deleted=False,
            license__confirmed=True,
            license__is_live=False,
        )
        .first()
    )
    if upload is None or upload.license.get_video_file() is not None:
        return
    emit(
        'licenses.nextcloud_download_pending',
        obj=upload.license,
        dedup_key=f'licenses.nextcloud_download_pending|{upload.pk}',
        payload={
            'number': upload.license.number,
            'filename': upload.filename,
            'uploaded_at': (
                upload.uploaded_at.isoformat() if upload.uploaded_at else ''),
            'url': admin_url(upload.license),
        },
    )


def on_nextcloud_video_saved(sender, instance, created, **kwargs):
    """Notify staff when an author upload needs a manual download."""
    if created:
        transaction.on_commit(lambda: _emit_nextcloud_pending(instance.pk))


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


def on_rental_saved(sender, instance, created, **kwargs):
    """Raise confirmation work and refresh today's rental expectations."""
    cache.delete('notifications:expectation:rental.pickup_due_today')
    cache.delete('notifications:expectation:rental.return_due_today')
    cache.delete('notifications:expectation:rental.room_due_today')
    if not created or instance.status != 'draft':
        return
    emit_on_commit(
        'rental.new_request',
        obj=instance,
        payload={
            'project_name': instance.project_name,
            'user': str(instance.user),
            'due_at': instance.requested_start_date.isoformat(),
            'url': links.rental_detail_url(instance.pk),
        },
    )


def on_room_rental_saved(sender, instance, **kwargs):
    """Refresh room-opening obligations after booking changes."""
    cache.delete('notifications:expectation:rental.room_due_today')


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
    """Report only failed jobs; successful completion needs no attention."""
    if instance.status != 'failed':
        return
    owner = getattr(instance, owner_field, None)
    if owner is None:
        return
    emit_on_commit(
        'tools.job_failed',
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


def on_day_plan_saved(sender, instance, created, **kwargs):
    """Evaluate broadcast assets as soon as a plan becomes committed."""
    cache.delete('notifications:expectation:planung.live_today')
    transaction.on_commit(refresh_missing_asset_events)


def connect_handlers() -> None:
    """Attach the handlers of the apps that are installed."""
    if apps.is_installed('licenses'):
        post_save.connect(
            on_license_saved,
            sender=apps.get_model('licenses.License'),
            dispatch_uid='notifications.licenses.new_unconfirmed',
        )
        post_save.connect(
            on_nextcloud_video_saved,
            sender=apps.get_model('licenses.NextcloudVideoFile'),
            dispatch_uid='notifications.licenses.nextcloud_pending',
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
            on_rental_saved,
            sender=apps.get_model('rental.RentalRequest'),
            dispatch_uid='notifications.rental.new_request',
        )
        post_save.connect(
            on_room_rental_saved,
            sender=apps.get_model('rental.RoomRental'),
            dispatch_uid='notifications.rental.room_due',
        )
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
    if apps.is_installed('planung') and apps.is_installed('media_files'):
        post_save.connect(
            on_day_plan_saved,
            sender=apps.get_model('planung.TagesPlan'),
            dispatch_uid='notifications.planung.missing_assets',
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
