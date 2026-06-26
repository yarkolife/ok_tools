"""Add the CoverTemplate rule model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0023_mediafilesconfig_cover_template_rules'),
    ]

    operations = [
        migrations.CreateModel(
            name='CoverTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Human-readable label for this rule.', max_length=255, verbose_name='Name')),
                ('scope', models.CharField(choices=[('series', 'Series (regex on title)'), ('category', 'Category (regex on category name)'), ('channel', 'Channel default (always matches)')], default='category', max_length=20, verbose_name='Scope')),
                ('match_pattern', models.CharField(blank=True, help_text='Regular expression. For "series" matched against the license title, for "category" against the category name. Leave empty for a channel default rule.', max_length=500, verbose_name='Match Pattern')),
                ('template', models.CharField(choices=[('base', 'Base'), ('journal', 'Journal (large episode number)'), ('trailer', 'Trailer (cinematic)')], default='base', max_length=20, verbose_name='Template')),
                ('theme', models.JSONField(blank=True, help_text='Optional overrides, e.g. {"accent": "#FF6B00", "background_style": "cinematic"}. background_style: bottom, bottom_left or cinematic.', null=True, verbose_name='Theme Overrides')),
                ('priority', models.IntegerField(default=100, help_text='Lower numbers are evaluated first (higher priority).', verbose_name='Priority')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cover Template Rule',
                'verbose_name_plural': 'Cover Template Rules',
                'ordering': ['priority', 'id'],
            },
        ),
    ]
