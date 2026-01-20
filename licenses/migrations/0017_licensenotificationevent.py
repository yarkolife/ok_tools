from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("licenses", "0016_licensesconfig_download_storage_path"),
    ]

    operations = [
        migrations.CreateModel(
            name="LicenseNotificationEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("license_number", models.IntegerField(db_index=True, help_text="License number used for matching and deduplication.", verbose_name="License number")),
                ("event_type", models.CharField(choices=[("video_uploaded", "Video uploaded"), ("draft_scheduled", "Draft scheduled"), ("planned_scheduled", "Planned scheduled"), ("contributions_available", "Contributions available")], db_index=True, max_length=64, verbose_name="Event type")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Created at")),
                ("payload", models.JSONField(blank=True, default=None, help_text="Optional structured data about the event (e.g., schedule time, filenames).", null=True, verbose_name="Payload")),
            ],
            options={
                "verbose_name": "License Notification Event",
                "verbose_name_plural": "License Notification Events",
            },
        ),
        migrations.AddConstraint(
            model_name="licensenotificationevent",
            constraint=models.UniqueConstraint(fields=("license_number", "event_type"), name="uniq_license_notification_event"),
        ),
    ]

