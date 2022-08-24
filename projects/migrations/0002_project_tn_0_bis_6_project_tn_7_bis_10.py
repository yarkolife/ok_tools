# Generated by Django 4.1 on 2022-08-22 12:31

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="tn_0_bis_6",
            field=models.IntegerField(default=0, verbose_name="bis 6 Jahre"),
        ),
        migrations.AddField(
            model_name="project",
            name="tn_7_bis_10",
            field=models.IntegerField(default=0, verbose_name="7-10 Jahre"),
        ),
    ]
