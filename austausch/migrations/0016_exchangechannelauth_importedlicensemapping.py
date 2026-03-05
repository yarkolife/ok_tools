from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0021_licensesconfig_create_videofile_on_nextcloud_download'),
        ('austausch', '0015_migrate_exported_licenses'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExchangeChannelAuth',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel_name', models.CharField(help_text='Channel name as used in exchange feed (case-insensitive).', max_length=100, unique=True, verbose_name='Channel Name')),
                ('supports_oktools_api', models.BooleanField(default=False, help_text='Enable metadata enrichment via remote OK-Tools API.', verbose_name='Supports OK-Tools API')),
                ('metadata_api_base_url', models.URLField(blank=True, help_text='Base URL of remote OK-Tools instance (e.g. https://portal.ok-magdeburg.de).', verbose_name='Metadata API Base URL')),
                ('metadata_api_token', models.CharField(blank=True, help_text='Token used for Authorization: Token <value>.', max_length=255, verbose_name='Metadata API Token')),
                ('request_timeout_seconds', models.PositiveIntegerField(default=10, help_text='HTTP timeout for metadata requests.', verbose_name='Request Timeout (seconds)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
                ('last_success_at', models.DateTimeField(blank=True, null=True, verbose_name='Last Success At')),
                ('last_error', models.TextField(blank=True, verbose_name='Last Error')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
            ],
            options={
                'verbose_name': 'Exchange Channel API Auth',
                'verbose_name_plural': 'Exchange Channel API Auth',
                'ordering': ['channel_name'],
            },
        ),
        migrations.CreateModel(
            name='ImportedLicenseMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_channel', models.CharField(help_text='Normalized exchange channel name.', max_length=100, verbose_name='Source Channel')),
                ('remote_license_number', models.PositiveIntegerField(verbose_name='Remote License Number')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('local_license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imported_license_mappings', to='licenses.license', verbose_name='Local License')),
            ],
            options={
                'verbose_name': 'Imported License Mapping',
                'verbose_name_plural': 'Imported License Mappings',
                'ordering': ['source_channel', 'remote_license_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='importedlicensemapping',
            constraint=models.UniqueConstraint(fields=('source_channel', 'remote_license_number'), name='austausch_unique_remote_license_per_channel'),
        ),
    ]
