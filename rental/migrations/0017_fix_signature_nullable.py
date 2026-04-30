from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0016_rentalrequest_signature_fields'),
    ]

    operations = [
        # Migration 0016 used SeparateDatabaseAndState(database_operations=[])
        # which updated Django's migration state but did NOT alter the actual DB.
        # The DB columns still have NOT NULL constraint for some fields.
        # Use RunSQL to force the ALTER TABLE statements.
        migrations.RunSQL(
            sql=[
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature DROP NOT NULL', None),
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature_svg DROP NOT NULL', None),
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature_points DROP NOT NULL', None),
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature_metadata DROP NOT NULL', None),
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature_method DROP NOT NULL', None),
                ('ALTER TABLE rental_rentalrequest ALTER COLUMN signature_signed_at DROP NOT NULL', None),
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
