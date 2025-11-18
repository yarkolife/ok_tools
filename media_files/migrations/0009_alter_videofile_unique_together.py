# Generated migration to change unique_together constraint
# Allows multiple files with same number in same storage (different paths/versions)

from django.db import migrations, models


def remove_old_unique_constraint(apps, schema_editor):
    """Safely remove old unique constraint if it exists."""
    with schema_editor.connection.cursor() as cursor:
        # Find and drop any unique constraint on (number, storage_location_id)
        cursor.execute("""
            SELECT conname 
            FROM pg_constraint 
            WHERE conrelid = 'media_files_videofile'::regclass
            AND contype = 'u'
            AND array_length(conkey, 1) = 2
            AND EXISTS (
                SELECT 1 
                FROM pg_attribute a1, pg_attribute a2
                WHERE a1.attrelid = conrelid 
                AND a1.attname = 'number'
                AND a1.attnum = ANY(conkey)
                AND a2.attrelid = conrelid
                AND a2.attname = 'storage_location_id'
                AND a2.attnum = ANY(conkey)
            );
        """)
        constraints = cursor.fetchall()
        for (constraint_name,) in constraints:
            cursor.execute(
                f"ALTER TABLE media_files_videofile DROP CONSTRAINT IF EXISTS {constraint_name};"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0008_alter_videofile_number'),
    ]

    operations = [
        # Safely remove old unique_together constraint if it exists in database
        migrations.RunPython(
            remove_old_unique_constraint,
            reverse_code=migrations.RunPython.noop,
        ),
        # Update Django's state to remove unique_together constraint (no DB operation)
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='videofile',
                    unique_together=set(),
                ),
            ],
        ),
        # Add new unique_together constraint (number, storage_location, file_path)
        # This allows multiple files with same number in same storage if they have different paths
        migrations.AlterUniqueTogether(
            name='videofile',
            unique_together={('number', 'storage_location', 'file_path')},
        ),
        # Add index for duplicate detection (number, storage_location)
        migrations.AddIndex(
            model_name='videofile',
            index=models.Index(fields=['number', 'storage_location'], name='media_files_number_storage_idx'),
        ),
    ]

