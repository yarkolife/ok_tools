# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0011_nextcloudvideofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='numeric_id',
            field=models.IntegerField(
                blank=True,
                help_text='Numeric ID used for import from external systems (e.g., 101, 102, 103)',
                null=True,
                unique=True,
                verbose_name='Numeric ID'
            ),
        ),
    ]
