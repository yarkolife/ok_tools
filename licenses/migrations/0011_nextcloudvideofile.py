# Generated manually for NextcloudVideoFile model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0010_add_is_live_field'),
    ]

    operations = [
        migrations.CreateModel(
            name='NextcloudVideoFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nextcloud_file_id', models.CharField(help_text='File ID or path in Nextcloud', max_length=500, verbose_name='Nextcloud File ID')),
                ('nextcloud_url', models.URLField(blank=True, help_text='Direct link to file in Nextcloud', max_length=1000, null=True, verbose_name='Nextcloud URL')),
                ('filename', models.CharField(help_text='Original filename', max_length=500, verbose_name='Filename')),
                ('file_size', models.BigIntegerField(blank=True, null=True, verbose_name='File Size (bytes)')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Uploaded at')),
                ('is_deleted', models.BooleanField(default=False, help_text='Flag if file was deleted from Nextcloud', verbose_name='Is Deleted')),
                ('deleted_at', models.DateTimeField(blank=True, help_text='When file was deleted from Nextcloud', null=True, verbose_name='Deleted at')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nextcloud_videos', to='licenses.license', verbose_name='License')),
            ],
            options={
                'verbose_name': 'Nextcloud Video File',
                'verbose_name_plural': 'Nextcloud Video Files',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]

