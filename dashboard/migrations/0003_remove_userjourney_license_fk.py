# Generated manually to remove orphan FK constraint

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove the foreign key constraint on dashboard_userjourney.license_id.

    The column was originally created as IntegerField in migration 0002,
    but somehow a FK constraint was added in the database. This migration
    drops the constraint so that License deletion does not fail.
    """

    dependencies = [
        ('dashboard', '0002_alertlog_alertthreshold_funnelmetrics_userjourney_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE dashboard_userjourney
                DROP CONSTRAINT IF EXISTS dashboard_userjourne_license_id_6eaad2ef_fk_licenses_;
            """,
            reverse_sql="""
                -- Re-add constraint if rolling back (optional, may fail if data inconsistent)
                ALTER TABLE dashboard_userjourney
                ADD CONSTRAINT dashboard_userjourne_license_id_6eaad2ef_fk_licenses_
                FOREIGN KEY (license_id) REFERENCES licenses_license(id)
                DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
    ]
