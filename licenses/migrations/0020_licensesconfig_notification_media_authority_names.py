# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licenses", "0019_nextcloudvideofile_user_uploaded"),
    ]

    operations = [
        migrations.AddField(
            model_name="licensesconfig",
            name="notification_media_authority_names",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Send status emails only to users whose profile belongs to one of these "
                "Media Authorities (Offene Kanäle/Bürgermedien). Empty = send to all. "
                "Use to restrict to \"our\" organisation(s) only.",
                verbose_name="Send notifications to (Media Authorities)",
            ),
        ),
    ]
