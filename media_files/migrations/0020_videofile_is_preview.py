# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0019_move_video_presets_to_tools'),
    ]

    operations = [
        migrations.AddField(
            model_name='videofile',
            name='is_preview',
            field=models.BooleanField(
                default=False,
                help_text='Short preview clip (e.g. 10s); not a full version, not linked to license',
                verbose_name='Preview version',
            ),
        ),
    ]
