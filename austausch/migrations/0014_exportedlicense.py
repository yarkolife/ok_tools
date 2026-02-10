"""Migration to add ExportedLicense model for unified export tracking."""

from django.db import migrations, models


def migrate_existing_exports(apps, schema_editor):
    """Migrate data from ExportToServerRun.details to ExportedLicense."""
    ExportedLicense = apps.get_model('austausch', 'ExportedLicense')
    ExportToServerRun = apps.get_model('austausch', 'ExportToServerRun')
    Contribution = apps.get_model('contributions', 'Contribution')

    license_numbers = set()

    for run in ExportToServerRun.objects.all():
        details = run.details or {}
        success_ids = details.get('success_ids', [])

        if run.mode == 'licenses':
            # success_ids are license numbers
            for sid in success_ids:
                try:
                    license_numbers.add(int(sid))
                except (ValueError, TypeError):
                    continue
        elif run.mode == 'contributions':
            # success_ids are contribution IDs - need to lookup license numbers
            contribs = Contribution.objects.filter(pk__in=success_ids).values_list(
                'license__number', flat=True
            )
            for num in contribs:
                if num is not None:
                    license_numbers.add(int(num))

    # Bulk create ExportedLicense records
    for num in license_numbers:
        ExportedLicense.objects.get_or_create(license_number=num)


def reverse_migration(apps, schema_editor):
    """Reverse migration - no-op since we can't reconstruct details."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0013_add_export_destination_network_share'),
        ('contributions', '0004_add_import_from_date_and_xls_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExportedLicense',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('license_number', models.PositiveIntegerField(
                    unique=True,
                    db_index=True,
                    verbose_name='License Number',
                    help_text='License number that was successfully exported to server'
                )),
                ('first_exported_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='First Exported At'
                )),
                ('last_exported_at', models.DateTimeField(
                    auto_now=True,
                    verbose_name='Last Exported At'
                )),
                ('export_count', models.PositiveIntegerField(
                    default=1,
                    verbose_name='Export Count',
                    help_text='Number of times this license was exported'
                )),
            ],
            options={
                'verbose_name': 'Exported License',
                'verbose_name_plural': 'Exported Licenses',
                'ordering': ['-last_exported_at'],
            },
        ),
        migrations.RunPython(migrate_existing_exports, reverse_migration),
    ]
