from django.conf import settings
from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('licenses', '0022_signature_v2_and_signing_session'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signingsession',
            name='license',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='signing_sessions',
                to='licenses.license',
                verbose_name='License',
            ),
        ),
        migrations.AddField(
            model_name='signingsession',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='signing_sessions',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Owner',
            ),
        ),
    ]
