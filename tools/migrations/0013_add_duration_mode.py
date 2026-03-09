"""Add duration_mode and audio_trim_mode to SlideshowProject."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0012_alter_toolsconfig_arnndn_model_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='slideshowproject',
            name='duration_mode',
            field=models.CharField(
                choices=[('music', 'By Music Duration'), ('images', 'By Image Duration')],
                default='music',
                help_text='Calculate video length by music or by image duration',
                max_length=10,
                verbose_name='Duration Mode',
            ),
        ),
        migrations.AddField(
            model_name='slideshowproject',
            name='audio_trim_mode',
            field=models.CharField(
                choices=[('fade', 'Fade Out'), ('trim', 'Trim to Fit')],
                default='fade',
                help_text='How to handle audio when images are shorter than music',
                max_length=10,
                verbose_name='Audio Trim Mode',
            ),
        ),
    ]
