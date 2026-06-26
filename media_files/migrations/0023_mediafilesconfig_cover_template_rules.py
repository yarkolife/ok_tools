"""Add cover_template_rules to MediaFilesConfig."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0022_mediafilesconfig_cover_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediafilesconfig',
            name='cover_template_rules',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Optional mapping of category name to cover template, e.g. {"Trailer": "trailer"}. Available: base, journal, trailer. Categories not listed use the base template.',
                verbose_name='Cover Template Rules',
            ),
        ),
    ]
