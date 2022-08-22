# Generated by Django 4.0.5 on 2022-08-18 09:55

from django.conf import settings
from django.db import migrations
from django.db import models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('licenses', '0007_alter_category_options_alter_licenserequest_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensetemplate',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='licenserequest',
            name='okuser',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL, verbose_name='User'),
        ),
    ]
