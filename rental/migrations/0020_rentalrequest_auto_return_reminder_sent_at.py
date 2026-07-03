from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0019_add_auto_reminder_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalrequest',
            name='auto_return_reminder_sent_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the automatic return reminder email was sent.',
                null=True,
                verbose_name='Automatic return reminder sent at',
            ),
        ),
    ]
