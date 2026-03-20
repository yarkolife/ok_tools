from django.db import migrations
from django.db import models


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0015_add_organizationconfig_logos'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationconfig',
            name='bundesland',
            field=models.CharField(
                choices=[
                    ('Baden-Württemberg', 'Baden-Württemberg'),
                    ('Bayern', 'Bayern'),
                    ('Berlin', 'Berlin'),
                    ('Brandenburg', 'Brandenburg'),
                    ('Bremen', 'Bremen'),
                    ('Hamburg', 'Hamburg'),
                    ('Hessen', 'Hessen'),
                    ('Mecklenburg-Vorpommern', 'Mecklenburg-Vorpommern'),
                    ('Niedersachsen', 'Niedersachsen'),
                    ('Nordrhein-Westfalen', 'Nordrhein-Westfalen'),
                    ('Rheinland-Pfalz', 'Rheinland-Pfalz'),
                    ('Saarland', 'Saarland'),
                    ('Sachsen', 'Sachsen'),
                    ('Sachsen-Anhalt', 'Sachsen-Anhalt'),
                    ('Schleswig-Holstein', 'Schleswig-Holstein'),
                    ('Thüringen', 'Thüringen'),
                ],
                default='Sachsen-Anhalt',
                help_text='German federal state written to exchange metadata',
                max_length=64,
                verbose_name='Bundesland',
            ),
        ),
        migrations.AddField(
            model_name='organizationconfig',
            name='bundesland_code',
            field=models.CharField(
                choices=[
                    ('BW', 'BW'),
                    ('BY', 'BY'),
                    ('BE', 'BE'),
                    ('BB', 'BB'),
                    ('HB', 'HB'),
                    ('HH', 'HH'),
                    ('HE', 'HE'),
                    ('MV', 'MV'),
                    ('NI', 'NI'),
                    ('NW', 'NW'),
                    ('RP', 'RP'),
                    ('SL', 'SL'),
                    ('SN', 'SN'),
                    ('ST', 'ST'),
                    ('SH', 'SH'),
                    ('TH', 'TH'),
                ],
                default='ST',
                help_text='Two-letter federal state code written to exchange metadata',
                max_length=2,
                verbose_name='Bundesland Code',
            ),
        ),
    ]
