# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('media_files', '0003_systemmanagementproxy_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='storagelocation',
            name='unc_path',
            field=models.CharField(blank=True, help_text='Windows UNC path (e.g., \\\\192.168.88.2\\Share) - optional', max_length=500, verbose_name='UNC Path'),
        ),
    ]

