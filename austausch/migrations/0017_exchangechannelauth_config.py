from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0016_exchangechannelauth_importedlicensemapping'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangechannelauth',
            name='config',
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='channel_auth_entries',
                to='austausch.exchangeconfig',
                verbose_name='Exchange Configuration',
            ),
        ),
    ]
