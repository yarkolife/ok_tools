# Generated by Django 4.1.3 on 2022-12-31 10:56

from django.db import migrations
from django.db import models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0003_alter_license_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='license',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
