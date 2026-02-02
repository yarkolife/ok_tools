# Generated manually for export-to-server feature

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0008_make_download_storage_path_optional'),
        ('registration', '0014_alter_mediaauthority_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeconfig',
            name='upload_server_path',
            field=models.CharField(
                blank=True,
                help_text='WebDAV path on Nextcloud for upload (e.g. GroupFolders/Mediathek-Upload/OK_MQ). Distinct from download/sync paths.',
                max_length=500,
                verbose_name='Upload Server Path',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='default_media_authority',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional "Offener Kanal" preselected for export.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='registration.mediaauthority',
                verbose_name='Default Media Authority',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='local_pdf_fallback_path',
            field=models.CharField(
                blank=True,
                help_text='Local directory for unsigned licenses; PDFs searched by pattern {number}_*.pdf (number at start of filename).',
                max_length=500,
                verbose_name='Local PDF Fallback Path',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='upload_thumbnail_enabled',
            field=models.BooleanField(
                default=False,
                help_text='If enabled, upload video cover/thumbnail images from a local directory when exporting to server.',
                verbose_name='Upload Thumbnail Enabled',
            ),
        ),
        migrations.AddField(
            model_name='exchangeconfig',
            name='thumbnail_storage_path',
            field=models.CharField(
                blank=True,
                help_text='Local directory where cover images are stored. Used when "Upload Thumbnail Enabled" is on. Matching by number at start of filename (e.g. 12345_cover.jpg). Supported: .jpg, .jpeg, .png, .webp.',
                max_length=500,
                verbose_name='Thumbnail Storage Path',
            ),
        ),
    ]
