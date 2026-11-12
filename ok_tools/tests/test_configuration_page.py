"""One configuration page; every settings form opens directly."""

from django.apps import apps
from django.contrib import admin
from django.urls import reverse
import pytest


def _config_models():
    return [model for model in admin.site._registry
            if callable(getattr(model, 'get_config', None))]


@pytest.mark.django_db
def test_page_lists_every_installed_settings_form(client, admin_user):
    client.force_login(admin_user)
    response = client.get(reverse('admin:configuration'), secure=True)
    html = response.content.decode()
    assert response.status_code == 200
    for model in _config_models():
        opts = model._meta
        assert reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist') in html
    # A module switched off in the environment is not installed, so it has no card.
    if not apps.is_installed('rental'):
        assert '/admin/rental/' not in html


@pytest.mark.django_db
def test_settings_list_opens_the_form(client, admin_user):
    client.force_login(admin_user)
    for model in _config_models():
        opts = model._meta
        response = client.get(
            reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist'), secure=True)
        config = model.get_config()
        assert response.status_code == 302, opts.label
        assert response['Location'] == reverse(
            f'admin:{opts.app_label}_{opts.model_name}_change', args=[config.pk])


@pytest.mark.django_db
def test_menu_has_one_configuration_entry(rf, admin_user):
    request = rf.get('/admin/')
    request.user = admin_user
    models = [m['object_name'] for app in admin.site.get_app_list(request) for m in app['models']]
    assert models.count('Configuration') == 1
    assert not {m.__name__ for m in _config_models()} & set(models)


@pytest.mark.django_db
def test_staff_without_settings_rights_sees_no_entry(rf, user):
    user.is_staff = True
    user.save()
    request = rf.get('/admin/')
    request.user = user
    models = [m['object_name'] for app in admin.site.get_app_list(request) for m in app['models']]
    assert 'Configuration' not in models
