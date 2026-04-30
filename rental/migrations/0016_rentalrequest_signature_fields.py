import uuid

from django.conf import settings
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0015_rentalconfig_employee_organizations_and_more'),
    ]

    # All schema changes were already applied by a previous (now-deleted)
    # migration. We use SeparateDatabaseAndState to sync the Django ORM
    # migration state without re-executing SQL against existing columns.
    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature',
                    field=models.TextField(
                        blank=True,
                        help_text='Base64 encoded signature image',
                        null=True,
                        verbose_name='Signature',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_svg',
                    field=models.TextField(
                        blank=True,
                        help_text='Primary SVG signature data',
                        null=True,
                        verbose_name='Signature SVG',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_points',
                    field=models.JSONField(
                        blank=True,
                        default=None,
                        help_text='Biometric signature stroke points (x,y,time,pressure).',
                        null=True,
                        verbose_name='Signature points',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_metadata',
                    field=models.JSONField(
                        blank=True,
                        default=None,
                        help_text='Signature metadata such as device, user-agent, and capture details.',
                        null=True,
                        verbose_name='Signature metadata',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_method',
                    field=models.CharField(
                        blank=True,
                        help_text='Signature input method (mouse, touch, stylus, qr_phone).',
                        max_length=32,
                        null=True,
                        verbose_name='Signature method',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_signed_at',
                    field=models.DateTimeField(
                        blank=True,
                        help_text='When the digital signature was captured.',
                        null=True,
                        verbose_name='Signature signed at',
                    ),
                ),
                migrations.CreateModel(
                    name='RentalSigningSession',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('token', models.CharField(db_index=True, default=uuid.uuid4, max_length=64, unique=True, verbose_name='Token')),
                        ('status', models.CharField(choices=[('pending', 'Pending'), ('signed', 'Signed'), ('expired', 'Expired')], db_index=True, default='pending', max_length=16, verbose_name='Status')),
                        ('expires_at', models.DateTimeField(db_index=True, verbose_name='Expires at')),
                        ('signature_svg', models.TextField(blank=True, null=True, verbose_name='Signature SVG')),
                        ('signature_points', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature points')),
                        ('signature_metadata', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature metadata')),
                        ('signature_method', models.CharField(blank=True, max_length=32, null=True, verbose_name='Signature method')),
                        ('signer_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='Signer IP')),
                        ('signer_user_agent', models.TextField(blank=True, null=True, verbose_name='Signer user agent')),
                        ('signed_at', models.DateTimeField(blank=True, null=True, verbose_name='Signed at')),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created at')),
                        ('owner', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='rental_signing_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
                        ('rental_request', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='signing_sessions', to='rental.rentalrequest', verbose_name='Rental request')),
                    ],
                    options={
                        'verbose_name': 'Rental Signing Session',
                        'verbose_name_plural': 'Rental Signing Sessions',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
            database_operations=[
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature',
                    field=models.TextField(
                        blank=True,
                        help_text='Base64 encoded signature image',
                        null=True,
                        verbose_name='Signature',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_svg',
                    field=models.TextField(
                        blank=True,
                        help_text='Primary SVG signature data',
                        null=True,
                        verbose_name='Signature SVG',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_points',
                    field=models.JSONField(
                        blank=True,
                        default=None,
                        help_text='Biometric signature stroke points (x,y,time,pressure).',
                        null=True,
                        verbose_name='Signature points',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_metadata',
                    field=models.JSONField(
                        blank=True,
                        default=None,
                        help_text='Signature metadata such as device, user-agent, and capture details.',
                        null=True,
                        verbose_name='Signature metadata',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_method',
                    field=models.CharField(
                        blank=True,
                        help_text='Signature input method (mouse, touch, stylus, qr_phone).',
                        max_length=32,
                        null=True,
                        verbose_name='Signature method',
                    ),
                ),
                migrations.AddField(
                    model_name='rentalrequest',
                    name='signature_signed_at',
                    field=models.DateTimeField(
                        blank=True,
                        help_text='When the digital signature was captured.',
                        null=True,
                        verbose_name='Signature signed at',
                    ),
                ),
                migrations.CreateModel(
                    name='RentalSigningSession',
                    fields=[
                        ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('token', models.CharField(db_index=True, default=uuid.uuid4, max_length=64, unique=True, verbose_name='Token')),
                        ('status', models.CharField(choices=[('pending', 'Pending'), ('signed', 'Signed'), ('expired', 'Expired')], db_index=True, default='pending', max_length=16, verbose_name='Status')),
                        ('expires_at', models.DateTimeField(db_index=True, verbose_name='Expires at')),
                        ('signature_svg', models.TextField(blank=True, null=True, verbose_name='Signature SVG')),
                        ('signature_points', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature points')),
                        ('signature_metadata', models.JSONField(blank=True, default=None, null=True, verbose_name='Signature metadata')),
                        ('signature_method', models.CharField(blank=True, max_length=32, null=True, verbose_name='Signature method')),
                        ('signer_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='Signer IP')),
                        ('signer_user_agent', models.TextField(blank=True, null=True, verbose_name='Signer user agent')),
                        ('signed_at', models.DateTimeField(blank=True, null=True, verbose_name='Signed at')),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Created at')),
                        ('owner', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='rental_signing_sessions', to=settings.AUTH_USER_MODEL, verbose_name='Owner')),
                        ('rental_request', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name='signing_sessions', to='rental.rentalrequest', verbose_name='Rental request')),
                    ],
                    options={
                        'verbose_name': 'Rental Signing Session',
                        'verbose_name_plural': 'Rental Signing Sessions',
                        'ordering': ['-created_at'],
                    },
                ),
            ],
        ),
    ]
