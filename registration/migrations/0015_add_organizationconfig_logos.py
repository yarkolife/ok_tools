from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0014_alter_mediaauthority_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationconfig',
            name='logo_large',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='organization/logos/',
                verbose_name='Large logo',
                help_text='Large logo displayed in the expanded sidebar',
            ),
        ),
        migrations.AddField(
            model_name='organizationconfig',
            name='logo_small',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='organization/logos/',
                verbose_name='Small logo',
                help_text='Square logo or SVG displayed in the collapsed sidebar',
            ),
        ),
    ]
