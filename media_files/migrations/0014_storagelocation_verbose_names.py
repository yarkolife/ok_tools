# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0013_change_created_at_verbose_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storagelocation',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Created at'),
        ),
        migrations.AlterField(
            model_name='storagelocation',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Updated at'),
        ),
    ]

