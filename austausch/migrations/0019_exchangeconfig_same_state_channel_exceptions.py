from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0018_exchangeitem_visibility_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeconfig',
            name='same_state_channel_exceptions',
            field=models.TextField(
                blank=True,
                help_text='Comma-separated or newline-separated channel names that should be treated as local/same-state for visibility rules.',
                verbose_name='Same-State Channel Exceptions',
            ),
        ),
    ]
