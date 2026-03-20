from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0017_exchangechannelauth_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeitem',
            name='allow_exchange',
            field=models.BooleanField(
                default=False,
                help_text='Visible for exchange within the same federal state',
                verbose_name='Allow Exchange',
            ),
        ),
        migrations.AddField(
            model_name='exchangeitem',
            name='allow_exchange_other_states',
            field=models.BooleanField(
                default=False,
                help_text='Visible for exchange from other federal states',
                verbose_name='Allow Exchange Other States',
            ),
        ),
        migrations.AddField(
            model_name='exchangeitem',
            name='bundesland',
            field=models.CharField(blank=True, max_length=64, verbose_name='Bundesland'),
        ),
        migrations.AddField(
            model_name='exchangeitem',
            name='bundesland_code',
            field=models.CharField(blank=True, max_length=2, verbose_name='Bundesland Code'),
        ),
    ]
