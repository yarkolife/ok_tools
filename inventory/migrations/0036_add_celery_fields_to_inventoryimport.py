# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0035_inventoryimport_items_updated'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryimport',
            name='task_id',
            field=models.CharField(
                blank=True,
                help_text='Celery task ID for asynchronous processing',
                max_length=255,
                null=True,
                verbose_name='Task ID'
            ),
        ),
        migrations.AddField(
            model_name='inventoryimport',
            name='celery_status',
            field=models.CharField(
                choices=[
                    ('not_started', 'Not Started'),
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('completed', 'Completed'),
                    ('completed_with_errors', 'Completed with Errors'),
                    ('failed', 'Failed'),
                    ('retry', 'Retry'),
                    ('revoked', 'Revoked')
                ],
                default='not_started',
                max_length=50,
                verbose_name='Celery Status'
            ),
        ),
    ]