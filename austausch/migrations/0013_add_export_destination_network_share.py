# Generated manually for network share export destination

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0012_alter_exchangeconfig_local_pdf_fallback_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeconfig',
            name='export_destination',
            field=models.CharField(
                choices=[('nextcloud', 'Nextcloud'), ('network_share', 'Network Share')],
                default='nextcloud',
                help_text='Select where export files should be written: Nextcloud or Network Share.',
                max_length=20,
                verbose_name='Export Destination',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='network_share_base_path',
            field=models.CharField(
                blank=True,
                help_text='Local mounted path inside container for network share export (e.g. /mnt/austausch_export/Vorschau/2025).',
                max_length=500,
                verbose_name='Network Share Base Path',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='network_share_subfolder',
            field=models.CharField(
                blank=True,
                default='austausch',
                help_text='Optional subfolder under base path. Leave empty to write directly into base path.',
                max_length=255,
                verbose_name='Network Share Subfolder',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='network_share_windows_root',
            field=models.CharField(
                blank=True,
                help_text='Windows path root used for files.txt entries (e.g. Z:\\Vorschau\\2025).',
                max_length=500,
                verbose_name='Network Share Windows Root',
            ),
        ),
    ]
