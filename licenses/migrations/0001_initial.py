# Generated by Django 4.0.5 on 2022-10-05 08:45

from django.db import migrations
from django.db import models
import datetime
import django.db.models.deletion
import licenses.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255,
                 unique=True, verbose_name='Category')),
            ],
            options={
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='License',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(
                    max_length=255, null=True, verbose_name='Title')),
                ('subtitle', models.CharField(blank=True,
                 max_length=255, null=True, verbose_name='Subtitle')),
                ('description', models.TextField(
                    null=True, verbose_name='Description')),
                ('further_persons', models.TextField(blank=True,
                 null=True, verbose_name='Further involved persons')),
                ('duration', models.DurationField(blank=True, default=datetime.timedelta(
                    0), help_text='Format: hh:mm:ss or mm:ss', verbose_name='Duration')),
                ('suggested_date', models.DateTimeField(blank=True,
                 null=True, verbose_name='Suggested broadcast date')),
                ('repetitions_allowed', models.BooleanField(
                    null=True, verbose_name='Repetitions allowed')),
                ('media_authority_exchange_allowed', models.BooleanField(
                    null=True, verbose_name='Media Authority exchange allowed')),
                ('youth_protection_necessary', models.BooleanField(
                    null=True, verbose_name='Youth protection necessary')),
                ('store_in_ok_media_library', models.BooleanField(
                    null=True, verbose_name='Store in OK media library')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('number', models.IntegerField(
                    default=1, unique=True, verbose_name='Number')),
                ('confirmed', models.BooleanField(
                    default=False, verbose_name='Confirmed')),
                ('is_screen_board', models.BooleanField(
                    default=False, verbose_name='Screen Board')),
                ('category', models.ForeignKey(default=licenses.models.default_category,
                 on_delete=django.db.models.deletion.CASCADE, to='licenses.category', verbose_name='Category')),
            ],
            options={
                'verbose_name': 'License Request',
                'verbose_name_plural': 'License Requests',
            },
        ),
    ]
