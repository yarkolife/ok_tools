"""Add cover-generation settings to MediaFilesConfig."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0021_alter_systemmanagementproxy_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Automatically generate video cover images (thumbnails) from a video frame plus license metadata and branding.',
                verbose_name='Cover Generation Enabled',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_logo_path',
            field=models.CharField(
                blank=True,
                help_text='Absolute path to the logo (PNG with alpha) drawn on covers. Leave empty to use the bundled default logo.',
                max_length=500,
                verbose_name='Cover Logo Path',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_title_font_path',
            field=models.CharField(
                blank=True,
                help_text='Absolute path to a .ttf font for headings. Leave empty to use the bundled default (Roboto-Bold).',
                max_length=500,
                verbose_name='Cover Title Font Path',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_body_font_path',
            field=models.CharField(
                blank=True,
                help_text='Absolute path to a .ttf font for body text (author, subtitle). Leave empty to use the bundled default (Roboto-Regular).',
                max_length=500,
                verbose_name='Cover Body Font Path',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_category_colors',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Optional mapping of category name to accent color hex, e.g. {"Magazin": "#E6007E"}. Categories not listed use a default palette.',
                verbose_name='Cover Category Colors',
            ),
        ),
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_output_dir',
            field=models.CharField(
                blank=True,
                help_text='Directory where generated covers are written as {number}_cover.jpg. Leave empty to use the austausch export thumbnail storage path.',
                max_length=500,
                verbose_name='Cover Output Directory',
            ),
        ),
    ]
