"""Passwords and API keys in configuration forms stay on the server."""

from django.forms import modelform_factory
from django.urls import reverse
from ok_tools.admin_secrets import secret_form
from planung.models import PlanungConfig
import pytest


SECRET = 'very-secret-key-123'


def _form_class():
    return secret_form(
        modelform_factory(PlanungConfig, fields=['playout_import_url', 'playout_import_api_key']),
        ['playout_import_api_key'],
    )


@pytest.mark.django_db
def test_stored_secret_is_not_rendered():
    config = PlanungConfig.get_config()
    config.playout_import_api_key = SECRET
    config.save()
    form = _form_class()(instance=config)
    html = str(form['playout_import_api_key'])
    assert SECRET not in html
    assert 'type="password"' in html
    assert 'A value is stored' in str(form.fields['playout_import_api_key'].help_text)


@pytest.mark.django_db
def test_empty_field_keeps_and_new_value_replaces_the_secret():
    config = PlanungConfig.get_config()
    config.playout_import_api_key = SECRET
    config.save()

    form = _form_class()(data={'playout_import_url': 'http://playout.example.org/api', 'playout_import_api_key': ''},
                         instance=config)
    assert form.is_valid(), form.errors
    form.save()
    config.refresh_from_db()
    assert config.playout_import_api_key == SECRET

    form = _form_class()(data={'playout_import_url': 'http://playout.example.org/api', 'playout_import_api_key': 'new'},
                         instance=config)
    assert form.is_valid(), form.errors
    form.save()
    config.refresh_from_db()
    assert config.playout_import_api_key == 'new'


@pytest.mark.django_db
def test_configuration_pages_do_not_show_secrets(client, django_user_model):
    from austausch.models import ExchangeConfig
    from tools.models import ToolsConfig

    admin = django_user_model.objects.create_superuser(email='root@example.org', password='x')
    client.force_login(admin)
    pages = []
    for model, field in ((PlanungConfig, 'anchor_render_api_key'),
                         (ExchangeConfig, 'nextcloud_password'),
                         (ToolsConfig, 'reel_render_api_key')):
        config = model.get_config()
        # update(): ExchangeConfig.save() validates fields this test does not need.
        model.objects.filter(pk=config.pk).update(**{field: SECRET})
        opts = model._meta
        pages.append(reverse(f'admin:{opts.app_label}_{opts.model_name}_change', args=[config.pk]))
    for url in pages:
        response = client.get(url)
        assert response.status_code == 200, url
        assert SECRET not in response.content.decode(), url
