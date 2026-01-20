# Generated manually for HEVC transcode settings

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0017_mediafilesconfig_supported_formats'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediafilesconfig',
            name='auto_transcode_hevc',
            field=models.BooleanField(
                default=False,
                help_text='Automatically transcode HEVC/H.265 videos to H.264 for browser playback compatibility',
                verbose_name='Auto Transcode HEVC',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='transcode_encode_preset',
            field=models.CharField(
                blank=True,
                default='1080p25_9000k',
                help_text='Default encoding preset for transcoding (e.g., "1080p25_9000k")',
                max_length=100,
                verbose_name='Transcode Encoding Preset',
            ),
        ),
    ]
