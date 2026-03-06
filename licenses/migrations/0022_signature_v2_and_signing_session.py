from django.db import migrations
from django.db import models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0021_licensesconfig_create_videofile_on_nextcloud_download'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='signature_metadata',
            field=models.JSONField(blank=True, default=None, help_text='Signature metadata such as device, user-agent, and capture details.', null=True, verbose_name='Signature metadata'),
        ),
        migrations.AddField(
            model_name='license',
            name='signature_method',
            field=models.CharField(blank=True, help_text='Signature input method (mouse, touch, stylus, qr_phone).', max_length=32, null=True, verbose_name='Signature method'),
        ),
        migrations.AddField(
            model_name='license',
            name='signature_points',
            field=models.JSONField(blank=True, default=None, help_text='Biometric signature stroke points (x,y,time,pressure).', null=True, verbose_name='Signature points'),
        ),
        migrations.AddField(
            model_name='license',
            name='signature_signed_at',
            field=models.DateTimeField(blank=True, help_text='When the digital signature was captured.', null=True, verbose_name='Signature signed at'),
        ),
        migrations.AddField(
            model_name='license',
            name='signature_svg',
            field=models.TextField(blank=True, help_text='Primary SVG signature data', null=True, verbose_name='Signature SVG'),
        ),
        migrations.CreateModel(
            name='SigningSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(db_index=True, default=uuid.uuid4, max_length=64, unique=True, verbose_name='Token')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('signed', 'Signed'), ('expired', 'Expired'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=16, verbose_name='Status')),
                ('expires_at', models.DateTimeField(db_index=True, verbose_name='Expires at')),
                ('signature_svg', models.TextField(blank=True, null=True, verbose_name='Signature SVG')),
                ('signature_points', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature points')),
                ('signature_metadata', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature metadata')),
                ('signature_method', models.CharField(blank=True, max_length=32, null=True, verbose_name='Signature method')),
                ('signer_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='Signer IP')),
                ('signer_user_agent', models.TextField(blank=True, null=True, verbose_name='Signer user agent')),
                ('signed_at', models.DateTimeField(blank=True, null=True, verbose_name='Signed at')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created at')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='signing_sessions', to='licenses.license', verbose_name='License')),
            ],
            options={
                'verbose_name': 'Signing Session',
                'verbose_name_plural': 'Signing Sessions',
                'ordering': ['-created_at'],
            },
        ),
    ]
