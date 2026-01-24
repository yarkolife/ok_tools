# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licenses", "0020_licensesconfig_notification_media_authority_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="licensesconfig",
            name="create_videofile_on_nextcloud_download",
            field=models.BooleanField(
                default=False,
                help_text="After downloading a Nextcloud video to disk, create a VideoFile in "
                "media_files so it shows as Player in the license list immediately. "
                "Requires MEDIA_FILES_ENABLED and the download path to be under a "
                "StorageLocation. If off, only the file is saved; a storage scan can "
                "create the VideoFile later.",
                verbose_name="Create VideoFile on Nextcloud download",
            ),
        ),
    ]
