# Generated manually on 2026-01-15 21:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('tools', '0001_initial'),
    ]

    operations = [
        # Add name field to SlideshowMedia
        migrations.AddField(
            model_name='slideshowmedia',
            name='name',
            field=models.CharField(blank=True, help_text='Name of the media file', max_length=255, verbose_name='Name'),
        ),
        # Add is_library field to SlideshowMedia
        migrations.AddField(
            model_name='slideshowmedia',
            name='is_library',
            field=models.BooleanField(default=False, help_text='Is this a library media file available to all projects?', verbose_name='Library File'),
        ),
        # Make project nullable for library files
        migrations.AlterField(
            model_name='slideshowmedia',
            name='project',
            field=models.ForeignKey(blank=True, help_text='Project this media belongs to (null for library files)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='media_files', to='tools.slideshowproject', verbose_name='Project'),
        ),
        # Add index for library files
        migrations.AddIndex(
            model_name='slideshowmedia',
            index=models.Index(fields=['is_library', 'media_type'], name='tools_slide_is_libr_345mno_idx'),
        ),
    ]
