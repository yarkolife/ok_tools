from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("licenses", "0017_licensenotificationevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="licensesconfig",
            name="send_status_emails",
            field=models.BooleanField(
                default=True,
                help_text="Send email notifications about video status (upload, scheduling, broadcast dates).",
                verbose_name="Send status emails",
            ),
        ),
    ]

