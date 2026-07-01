from django.db import migrations
from django.db import models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0017_toolsconfig_reel_output_storage_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='toolsconfig',
            name='reel_reminder_enabled',
            field=models.BooleanField(
                default=False,
                help_text="Send one daily email with today's reel download links.",
                verbose_name='Daily reel reminder enabled',
            ),
        ),
        migrations.AddField(
            model_name='toolsconfig',
            name='reel_reminder_recipient_email',
            field=models.EmailField(
                blank=True,
                default='',
                help_text='Email address that receives the daily reel reminder.',
                max_length=254,
                verbose_name='Daily reel reminder recipient',
            ),
        ),
        migrations.AddField(
            model_name='toolsconfig',
            name='reel_reminder_time',
            field=models.TimeField(
                default=datetime.time(9, 0),
                help_text='Local time when Celery Beat should send the daily reminder.',
                verbose_name='Daily reel reminder time',
            ),
        ),
    ]
