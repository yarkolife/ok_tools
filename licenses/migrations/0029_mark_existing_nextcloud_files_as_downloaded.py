"""Mark files that existed before the automatic download as handled."""

from django.db import migrations


def mark_existing_as_downloaded(apps, schema_editor):
    """
    Keep the automation away from the archive.

    Files uploaded before this feature were fetched manually (or on purpose
    not at all), so they must not be pulled from Nextcloud in bulk by the
    catch-up sweep. Only uploads from now on are downloaded automatically —
    exactly once. Everything else stays a manual decision in the admin.
    """
    NextcloudVideoFile = apps.get_model('licenses', 'NextcloudVideoFile')

    for video in NextcloudVideoFile.objects.filter(downloaded_at__isnull=True).iterator():
        NextcloudVideoFile.objects.filter(pk=video.pk).update(
            downloaded_at=video.uploaded_at,
        )


def unmark(apps, schema_editor):
    """Reverse: forget the marker again."""
    NextcloudVideoFile = apps.get_model('licenses', 'NextcloudVideoFile')
    NextcloudVideoFile.objects.filter(local_path='').update(downloaded_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0028_licensesconfig_auto_download_to_storage_and_more'),
    ]

    operations = [
        migrations.RunPython(mark_existing_as_downloaded, unmark),
    ]
