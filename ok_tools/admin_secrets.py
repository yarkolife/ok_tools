"""Passwords, API keys and tokens in admin forms are never sent back to the browser."""

from django import forms
from django.utils.translation import gettext_lazy as _


STORED_HINT = _('A value is stored. Leave empty to keep it; enter a new one to replace it.')


def secret_form(form_class, names):
    """Subclass of ``form_class`` that shows ``names`` as empty password inputs.

    An empty field on save keeps the stored value of the instance, a new value
    replaces it. The page only says whether a value is stored.
    """
    names = [name for name in names if name in form_class.base_fields]
    if not names:
        return form_class

    class SecretForm(form_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for name in names:
                field = self.fields[name]
                attrs = dict(getattr(field.widget, 'attrs', {}) or {})
                attrs['autocomplete'] = 'new-password'
                field.widget = forms.PasswordInput(render_value=False, attrs=attrs)
                field.required = False
                if getattr(self.instance, name, ''):
                    field.help_text = STORED_HINT

        def clean(self):
            data = super().clean()
            for name in names:
                # self.instance still holds the stored values here; the form
                # data is copied onto it only after clean().
                stored = getattr(self.instance, name, '') if self.instance.pk else ''
                if not data.get(name) and stored:
                    data[name] = stored
            return data

    SecretForm.__name__ = form_class.__name__
    return SecretForm


class SecretFieldsMixin:
    """ModelAdmin: the fields in ``secret_fields`` are write-only."""

    secret_fields: tuple = ()

    def get_form(self, request, obj=None, **kwargs):
        return secret_form(super().get_form(request, obj, **kwargs), self.secret_fields)


class SecretFieldsInlineMixin:
    """Inline: the fields in ``secret_fields`` are write-only in every row."""

    secret_fields: tuple = ()

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form = secret_form(formset.form, self.secret_fields)
        return formset
