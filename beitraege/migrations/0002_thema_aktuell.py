"""A broad default topic for posts that fit no special topic."""

from django.db import migrations


def create(apps, schema_editor):
    Thema = apps.get_model('beitraege', 'Thema')
    Thema.objects.get_or_create(name='Aktuell', defaults={'position': 0})


class Migration(migrations.Migration):

    dependencies = [
        ('beitraege', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create, migrations.RunPython.noop),
    ]
