# Generated manually: second PDF fallback path for export to server

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('austausch', '0009_add_export_to_server_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='exchangeconfig',
            name='local_pdf_fallback_path_2',
            field=models.CharField(
                blank=True,
                help_text='Second local directory for unsigned licenses; searched if not found in first path.',
                max_length=500,
                verbose_name='Local PDF Fallback Path (2)',
            ),
        ),
    ]
