import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0019_move_video_presets_to_tools'),
        ('tools', '0016_alter_toolsconfig_reel_render_timeout'),
    ]

    operations = [
        migrations.AddField(
            model_name='toolsconfig',
            name='reel_output_storage',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='media_files.storagelocation',
                help_text=(
                    'Storage location where the renderer writes finished reels. '
                    'When empty, the first Playout storage is used. Needed for '
                    'preview/download.'
                ),
                verbose_name='Reel output storage',
            ),
        ),
        migrations.AddField(
            model_name='toolsconfig',
            name='reel_output_subdir',
            field=models.CharField(
                blank=True,
                default='003_Programmvorschau',
                max_length=255,
                help_text=(
                    'Subdirectory inside the output storage where reels are written.'
                ),
                verbose_name='Reel output subdirectory',
            ),
        ),
    ]
