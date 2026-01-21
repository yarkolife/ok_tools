# Generated manually

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0006_remove_sync_schedule'),
        ('media_files', '0015_alter_videofile_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeconfig',
            name='storage_location',
            field=models.ForeignKey(
                blank=True,
                help_text='Select existing storage location for imported files. If not set, a new storage will be created automatically.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='media_files.storagelocation',
                verbose_name='Storage Location'
            ),
        ),
        migrations.AlterField(
            model_name='exchangeconfig',
            name='download_storage_path',
            field=models.CharField(
                help_text='Local path for downloaded files before import (used if storage location is not set)',
                max_length=500,
                verbose_name='Download Storage Path'
            ),
        ),
    ]
