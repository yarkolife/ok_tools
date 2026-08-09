from django.db import migrations


def seed_from_exchange(apps, schema_editor):
    """Copy the own media authority from the exchange configuration.

    Which "Offener Kanal" an installation is belongs to the organization,
    not to the exchange module -- a channel may not use the exchange at all.
    Deployments that configured it there keep their value.
    """
    try:
        ExchangeConfig = apps.get_model('austausch', 'ExchangeConfig')
    except LookupError:
        # The exchange module is not installed in this deployment.
        return

    OrganizationConfig = apps.get_model('registration', 'OrganizationConfig')
    exchange_config = ExchangeConfig.objects.exclude(
        default_media_authority__isnull=True).first()
    if exchange_config is None:
        return

    OrganizationConfig.objects.filter(media_authority__isnull=True).update(
        media_authority=exchange_config.default_media_authority_id)


def unseed(apps, schema_editor):
    """Reverse step: clear the field again."""
    OrganizationConfig = apps.get_model('registration', 'OrganizationConfig')
    OrganizationConfig.objects.update(media_authority=None)


class Migration(migrations.Migration):

    dependencies = [
        ('registration', '0019_organizationconfig_media_authority'),
    ]

    operations = [
        migrations.RunPython(seed_from_exchange, unseed),
    ]
