from datetime import time

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0012_rentalconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalconfig',
            name='friday_end_time',
            field=models.TimeField(blank=True, default=time(18, 0), null=True, verbose_name='Friday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='friday_start_time',
            field=models.TimeField(blank=True, default=time(10, 0), null=True, verbose_name='Friday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='monday_end_time',
            field=models.TimeField(blank=True, default=time(18, 0), null=True, verbose_name='Monday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='monday_start_time',
            field=models.TimeField(blank=True, default=time(10, 0), null=True, verbose_name='Monday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='saturday_end_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Saturday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='saturday_start_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Saturday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='sunday_end_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Sunday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='sunday_start_time',
            field=models.TimeField(blank=True, null=True, verbose_name='Sunday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='thursday_end_time',
            field=models.TimeField(blank=True, default=time(18, 0), null=True, verbose_name='Thursday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='thursday_start_time',
            field=models.TimeField(blank=True, default=time(10, 0), null=True, verbose_name='Thursday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='tuesday_end_time',
            field=models.TimeField(blank=True, default=time(18, 0), null=True, verbose_name='Tuesday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='tuesday_start_time',
            field=models.TimeField(blank=True, default=time(10, 0), null=True, verbose_name='Tuesday opening time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='wednesday_end_time',
            field=models.TimeField(blank=True, default=time(18, 0), null=True, verbose_name='Wednesday closing time'),
        ),
        migrations.AddField(
            model_name='rentalconfig',
            name='wednesday_start_time',
            field=models.TimeField(blank=True, default=time(10, 0), null=True, verbose_name='Wednesday opening time'),
        ),
    ]
