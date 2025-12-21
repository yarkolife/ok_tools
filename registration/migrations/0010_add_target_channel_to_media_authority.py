# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0009_alter_mediaauthority_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediaauthority',
            name='target_channel',
            field=models.CharField(
                blank=True,
                help_text='Target channel identifier (e.g., "@ok_dessau@lokalmedial.de")',
                max_length=255,
                null=True,
                unique=True,
                verbose_name='Target Channel'
            ),
        ),
    ]
