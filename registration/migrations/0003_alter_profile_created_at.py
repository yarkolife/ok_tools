# Generated by Django 4.0.5 on 2022-08-29 14:14

from django.db import migrations
from django.db import models
from django.utils.timezone import utc
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0002_alter_profile_birthday_alter_profile_created_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='created_at',
            field=models.DateTimeField(default=datetime.datetime(
                2022, 8, 29, 14, 14, 17, 960051, tzinfo=utc)),
        ),
    ]
