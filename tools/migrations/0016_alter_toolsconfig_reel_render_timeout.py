from django.db import migrations, models


def bump_timeout(apps, schema_editor):
    """Raise the reel render timeout from the old default (30) to 360."""
    ToolsConfig = apps.get_model('tools', 'ToolsConfig')
    ToolsConfig.objects.filter(reel_render_timeout=30).update(reel_render_timeout=360)


def restore_timeout(apps, schema_editor):
    ToolsConfig = apps.get_model('tools', 'ToolsConfig')
    ToolsConfig.objects.filter(reel_render_timeout=360).update(reel_render_timeout=30)


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0015_toolsconfig_reel_default_mediathek_zeile1_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='toolsconfig',
            name='reel_render_timeout',
            field=models.PositiveIntegerField(
                default=360,
                help_text=(
                    'HTTP read timeout for reel render/start and hook requests. '
                    'Must be generous (e.g. 360) so a cold AI model is not cut '
                    'off before the renderer responds.'
                ),
                verbose_name='Reel render timeout (seconds)',
            ),
        ),
        migrations.RunPython(bump_timeout, restore_timeout),
    ]
