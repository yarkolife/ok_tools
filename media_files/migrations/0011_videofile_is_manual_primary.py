# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0010_presetoverlay_videopreset_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='videofile',
            name='is_manual_primary',
            field=models.BooleanField(
                default=False,
                help_text='Manually marked as primary version (overrides automatic selection)',
                verbose_name='Manual Primary'
            ),
        ),
    ]

