# Generated manually: ExportToServerRun model for export result report

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('austausch', '0010_add_local_pdf_fallback_path_2'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportToServerRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Started at')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed at')),
                ('mode', models.CharField(
                    choices=[('contributions', 'By contributions'), ('licenses', 'By license numbers')],
                    max_length=20,
                    verbose_name='Mode',
                )),
                ('total_count', models.PositiveIntegerField(default=0, verbose_name='Total selected')),
                ('success_count', models.PositiveIntegerField(default=0, verbose_name='Uploaded')),
                ('failure_count', models.PositiveIntegerField(default=0, verbose_name='Failed')),
                ('skipped_no_pdf_count', models.PositiveIntegerField(
                    default=0,
                    verbose_name='Skipped (no PDF)',
                )),
                ('details', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='success_ids, failed (id, reason), skipped_no_pdf',
                    verbose_name='Details',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='User',
                )),
            ],
            options={
                'ordering': ['-started_at'],
                'verbose_name': 'Export to server run',
                'verbose_name_plural': 'Export to server runs',
            },
        ),
    ]
