from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0023_signingsession_owner_and_optional_license'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='mediathek_url',
            field=models.URLField(blank=True, null=True, verbose_name='Mediathek URL'),
        ),
        migrations.AddField(
            model_name='license',
            name='mediathek_url_updated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Mediathek URL updated at'),
        ),
    ]
