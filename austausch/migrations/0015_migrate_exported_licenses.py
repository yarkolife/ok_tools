"""Migration to populate ExportedLicense from existing ExportToServerRun data."""

from django.db import migrations


def migrate_exported_licenses(apps, schema_editor):
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
    """Reverse migration - no-op."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0014_exportedlicense'),
    ]

    operations = [
        migrations.RunPython(migrate_exported_licenses, reverse_migration),
    ]
