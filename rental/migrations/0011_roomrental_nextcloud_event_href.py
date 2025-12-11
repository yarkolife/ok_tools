# Generated manually for Nextcloud Calendar integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0010_roomrental_requested_end_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomrental',
            name='nextcloud_event_href',
            field=models.URLField(
                blank=True,
                null=True,
                help_text='URL of the event in Nextcloud Calendar (for CalDAV sync)',
                verbose_name='Nextcloud Event URL'
            ),
        ),
    ]


