from django.db import migrations


# The layout every seeded format starts with: what the item is called and who
# owns it above the bars, the location last, where its codes print largest.
DEFAULT_LINES = [
    {'position': 10, 'content': 'number_owner', 'size': 'normal'},
    {'position': 20, 'content': 'barcode', 'size': 'normal'},
    {'position': 30, 'content': 'description', 'size': 'normal'},
    {'position': 40, 'content': 'location', 'size': 'small'},
]


def seed(apps, schema_editor):
    LabelFormat = apps.get_model('rental', 'LabelFormat')
    LabelLine = apps.get_model('rental', 'LabelLine')
    for label_format in LabelFormat.objects.all():
        if label_format.lines.exists():
            continue
        for line in DEFAULT_LINES:
            LabelLine.objects.create(label_format=label_format, **line)


def unseed(apps, schema_editor):
    LabelLine = apps.get_model('rental', 'LabelLine')
    LabelLine.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0028_label_line'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
