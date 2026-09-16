from django.db import migrations


class Migration(migrations.Migration):
    """Drop the ``device_name`` column left over on some databases.

    Migration 0029 removed the field from the model, but on databases where the
    schema was restored from an older dump the column is still present with a
    ``NOT NULL`` constraint, which breaks every insert into the table.
    """

    dependencies = [
        ('inventory', '0043_inventoryitem_notes'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE inventory_inspection '
                'DROP COLUMN IF EXISTS device_name;',
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[],
        ),
    ]
