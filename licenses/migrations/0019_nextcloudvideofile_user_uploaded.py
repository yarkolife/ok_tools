# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licenses", "0018_licensesconfig_send_status_emails"),
    ]

    operations = [
        migrations.AddField(
            model_name="nextcloudvideofile",
            name="user_uploaded",
            field=models.BooleanField(
                default=False,
                help_text="True if the file was uploaded by the rightsholder via the portal; "
                "False if created by staff (e.g. in Admin). Used to decide whether to "
                "send draft_scheduled, planned_scheduled, contributions_available emails.",
                verbose_name="User uploaded",
            ),
        ),
    ]
