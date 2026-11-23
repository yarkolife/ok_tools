"""The periodic tasks are named in German; the module is now called "Posts".

``BeitragsConfig.sync_periodic_task`` finds the tasks by name, so the old
names are renamed instead of leaving two tasks for the same job.
"""

from django.db import migrations

RENAMES = {
    'Beiträge: freigegebene Beiträge veröffentlichen': 'Posts: freigegebene Posts veröffentlichen',
    'Beiträge: per E-Mail gesendete Beiträge abholen': 'Posts: per E-Mail gesendete Posts abholen',
}


def rename(apps, schema_editor, pairs):
    try:
        PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    except LookupError:
        return
    for old, new in pairs.items():
        if PeriodicTask.objects.filter(name=new).exists():
            PeriodicTask.objects.filter(name=old).delete()
        else:
            PeriodicTask.objects.filter(name=old).update(name=new)


def forwards(apps, schema_editor):
    rename(apps, schema_editor, RENAMES)


def backwards(apps, schema_editor):
    rename(apps, schema_editor, {new: old for old, new in RENAMES.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('beitraege', '0003_mail_intake'),
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
