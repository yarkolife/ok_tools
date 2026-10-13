"""Track when a license was last changed, for the playout metadata sync."""

from django.db import migrations
from django.db import models
from django.db.models import F
import django.utils.timezone


def copy_created_at(apps, schema_editor):
    """Start existing licenses at their creation time, not at migration time."""
    License = apps.get_model('licenses', 'License')
    License.objects.update(updated_at=F('created_at'))


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0031_seed_youth_protection_windows'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='updated_at',
            field=models.DateTimeField(
                auto_now=True,
                db_index=True,
                default=django.utils.timezone.now,
                verbose_name='Updated at',
            ),
            preserve_default=False,
        ),
        migrations.RunPython(copy_created_at, migrations.RunPython.noop),
    ]
