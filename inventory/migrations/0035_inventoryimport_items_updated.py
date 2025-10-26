# Generated manually for inventory_import refactoring

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0034_merge_20250819_1733'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryimport',
            name='items_updated',
            field=models.PositiveIntegerField(default=0, verbose_name='Items Updated'),
        ),
    ]