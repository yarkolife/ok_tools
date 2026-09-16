from django.db import migrations


# The two roll sizes the module shipped with. Their slugs are the format keys
# the print URL already used, so links handed out before this migration keep
# working.
SEED = [
    {
        'slug': 'roll_51x25',
        'name': 'Roll label',
        'width_mm': 51,
        'height_mm': 25,
        'sort_order': 10,
    },
    {
        'slug': 'roll_70x32',
        'name': 'Roll label',
        'width_mm': 70,
        'height_mm': 32,
        'sort_order': 20,
    },
]


def seed(apps, schema_editor):
    LabelFormat = apps.get_model('rental', 'LabelFormat')
    for entry in SEED:
        LabelFormat.objects.get_or_create(
            slug=entry['slug'], defaults=entry)


def unseed(apps, schema_editor):
    LabelFormat = apps.get_model('rental', 'LabelFormat')
    LabelFormat.objects.filter(
        slug__in=[entry['slug'] for entry in SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0026_label_format'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
