# Generated by Django 4.1.3 on 2022-12-20 12:50

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_alter_project_media_education_supervisors_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='media_education_supervisors',
            field=models.ManyToManyField(
                blank=True, to='projects.mediaeducationsupervisor', verbose_name='Media education supervisors'),
        ),
    ]
