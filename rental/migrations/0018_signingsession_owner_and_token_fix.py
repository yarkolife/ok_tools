from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0017_fix_signature_nullable'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                (
                    'ALTER TABLE rental_rentalsigningsession '
                    'ADD COLUMN IF NOT EXISTS owner_id integer '
                    'REFERENCES registration_okuser(id) DEFERRABLE INITIALLY DEFERRED',
                    None,
                ),
                (
                    'ALTER TABLE rental_rentalsigningsession '
                    "ALTER COLUMN token TYPE varchar(64) USING token::text",
                    None,
                ),
                (
                    'ALTER TABLE rental_rentalsigningsession '
                    "ALTER COLUMN token SET DEFAULT ''",
                    None,
                ),
                (
                    'ALTER TABLE rental_rentalsigningsession '
                    'ALTER COLUMN rental_request_id DROP NOT NULL',
                    None,
                ),
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]