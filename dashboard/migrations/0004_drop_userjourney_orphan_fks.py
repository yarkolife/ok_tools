"""Drop leftover foreign keys on the UserJourney reference columns.

``rental_request_id``, ``license_id`` and ``contribution_id`` are plain
integers in the model (the dashboard works without those modules), but some
databases still carry FK constraints on them from an older schema. Then
deleting a rental request or a contribution that appears in a user's journey
fails with an IntegrityError. 0003 removed the one on ``license_id`` by name;
this looks the constraints up instead, so any leftover name is caught.
"""

from django.db import migrations


COLUMNS = ('rental_request_id', 'license_id', 'contribution_id')


def drop_orphan_fks(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT con.conname
              FROM pg_constraint con
              JOIN pg_attribute att
                ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
             WHERE con.conrelid = 'dashboard_userjourney'::regclass
               AND con.contype = 'f'
               AND att.attname = ANY (%s)
            """,
            [list(COLUMNS)],
        )
        names = [row[0] for row in cursor.fetchall()]
        for name in names:
            cursor.execute(
                'ALTER TABLE dashboard_userjourney DROP CONSTRAINT IF EXISTS %s'
                % schema_editor.quote_name(name))


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0003_remove_userjourney_license_fk'),
    ]

    operations = [
        migrations.RunPython(drop_orphan_fks, migrations.RunPython.noop),
    ]
