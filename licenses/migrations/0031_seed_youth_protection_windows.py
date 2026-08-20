"""Seed the default broadcast windows for youth protection categories."""

from django.db import migrations
import datetime


DEFAULTS = {
    'from_12': (datetime.time(20, 0), datetime.time(6, 0)),
    'from_16': (datetime.time(22, 0), datetime.time(6, 0)),
    'from_18': (datetime.time(23, 0), datetime.time(6, 0)),
}


def seed_windows(apps, schema_editor):
    """Create one row per restricted category, leaving existing rows alone."""
    YouthProtectionWindow = apps.get_model('licenses', 'YouthProtectionWindow')
    for category, (start_time, end_time) in DEFAULTS.items():
        YouthProtectionWindow.objects.get_or_create(
            category=category,
            defaults={
                'enabled': True,
                'start_time': start_time,
                'end_time': end_time,
            },
        )


def drop_windows(apps, schema_editor):
    """Remove only the seeded categories again."""
    YouthProtectionWindow = apps.get_model('licenses', 'YouthProtectionWindow')
    YouthProtectionWindow.objects.filter(category__in=DEFAULTS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0030_youth_protection_window'),
    ]

    operations = [
        migrations.RunPython(seed_windows, drop_windows),
    ]
