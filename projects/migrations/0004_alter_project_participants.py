# Generated by Django 4.1.2 on 2022-11-18 15:05

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0003_alter_project_participants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='participants',
            field=models.JSONField(default={'7 bis 10': {'d': 0, 'k.A.': 0, 'm': 0, 'w': 0}, 'bis 6': {
                                   'd': 0, 'k.A.': 0, 'm': 0, 'w': 0}}, verbose_name='participants'),
        ),
    ]
