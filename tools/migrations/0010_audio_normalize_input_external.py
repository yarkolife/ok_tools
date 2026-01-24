# Generated manually for input from storage outside MEDIA_ROOT

import django.core.validators
from django.db import migrations, models
import tools.models


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0009_rename_tools_audio_created_7c0c12_idx_tools_audio_created_ff2115_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='audionormalizejob',
            name='input_path_external',
            field=models.CharField(
                blank=True,
                help_text='Absolute path when input is outside MEDIA_ROOT (e.g. from a storage location).',
                max_length=1000,
                verbose_name='Input path (external)',
            ),
        ),
        migrations.AddField(
            model_name='audionormalizejob',
            name='input_media_file_id',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='media_files.VideoFile ID when input was chosen by media number (for stream URL).',
                null=True,
                verbose_name='Input media file ID',
            ),
        ),
        migrations.AlterField(
            model_name='audionormalizejob',
            name='input_file',
            field=models.FileField(
                blank=True,
                upload_to=tools.models.audio_normalize_input_upload_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=['mp4', 'mov', 'mkv', 'avi', 'webm', 'm4v', 'mp3', 'wav', 'm4a', 'flac', 'ogg']
                    )
                ],
                verbose_name='Input File',
            ),
        ),
    ]
