# Generated by Django 4.1.2 on 2022-11-18 15:00

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='participants',
            field=models.JSONField(default=0, verbose_name='participants'),
        ),
    ]
