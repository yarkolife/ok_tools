# Generated manually - restore unique_together constraint
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0006_systemmanagementproxy_and_more'),
    ]

    operations = [
        # Ensure unique_together constraint exists
        # This may have been removed by migration 0006's RunSQL
        migrations.AlterUniqueTogether(
            name='videofile',
            unique_together={('number', 'storage_location')},
        ),
    ]
