# Generated migration to change unique_together constraint
# Allows multiple files with same number in same storage (different paths/versions)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0008_alter_videofile_number'),
    ]

    operations = [
        # Remove old unique_together constraint (number, storage_location)
        migrations.AlterUniqueTogether(
            name='videofile',
            unique_together=set(),
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

