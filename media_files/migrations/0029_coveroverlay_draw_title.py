"""Add CoverOverlay draw_title option."""

from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    """Migration adding optional title rendering control to cover overlays."""

    dependencies = [
        ('media_files', '0028_mediafilesconfig_cover_logo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='coveroverlay',
            name='draw_title',
            field=models.BooleanField(
                default=True,
                help_text=_(
                    'Aus, wenn die Grafik bereits Text enthält oder dieser '
                    'Cover-Typ ohne Lizenz-Titel gerendert werden soll.'),
                verbose_name=_('Titel zeichnen'),
            ),
        ),
    ]
