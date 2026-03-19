from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0013_rentalconfig_working_hours'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalitem',
            name='pick_list_checked',
            field=models.BooleanField(default=False, verbose_name='Pick list checked'),
        ),
        migrations.AddField(
            model_name='rentalitem',
            name='pick_list_note',
            field=models.TextField(blank=True, verbose_name='Pick list note'),
        ),
    ]
