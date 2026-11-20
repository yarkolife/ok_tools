"""Form of the mobile page "Neuer Beitrag"."""

from .models import PLATFORM_CHOICES
from .models import Beitrag
from .models import BeitragsConfig
from .models import Thema
from .services import images
from django import forms
from django.utils.translation import gettext_lazy as _


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    """Several photos from the camera or the gallery."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*,.heic,.heif'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        cleaned = [super(MultiplePhotoField, self).clean(f, initial) for f in files]
        if len(cleaned) > Beitrag.MAX_PHOTOS:
            raise forms.ValidationError(_('At most %(max)s photos.') % {'max': Beitrag.MAX_PHOTOS})
        for upload in cleaned:
            if not images.is_readable(upload):
                raise forms.ValidationError(
                    _('%(name)s is not a photo that can be read (JPEG, PNG, HEIC).') % {'name': upload.name})
        return cleaned


class NeuerBeitragForm(forms.Form):
    thema = forms.ModelChoiceField(queryset=Thema.objects.none(), label=_('Topic'),
                                   empty_label=None)
    titel = forms.CharField(max_length=200, label=_('Title'))
    text = forms.CharField(widget=forms.Textarea(attrs={'rows': 8}), label=_('Text'))
    link = forms.URLField(required=False, label=_('Link'),
                          help_text=_('E.g. the Mediathek; clickable on Facebook and the website.'))
    fotos = MultiplePhotoField(required=False, label=_('Photos'),
                               help_text=_('Up to 10 photos; the first one is the cover.'))
    einwilligung = forms.BooleanField(
        required=False, label=_('Everybody recognisable on the photos agreed to the publication.'))
    plattformen = forms.MultipleChoiceField(
        choices=PLATFORM_CHOICES, widget=forms.CheckboxSelectMultiple, required=False,
        label=_('Publish on'))
    publish_at = forms.DateTimeField(
        required=False, label=_('Publish at'),
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
        help_text=_('Empty: right after the approval.'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['thema'].queryset = Thema.objects.filter(is_active=True)
        available = BeitragsConfig.get_config().configured_platforms()
        self.fields['plattformen'].choices = [c for c in PLATFORM_CHOICES if c[0] in available]
        if not self.is_bound:
            self.fields['plattformen'].initial = available

    def clean(self):
        data = super().clean()
        if data.get('fotos') and not data.get('einwilligung'):
            self.add_error('einwilligung', _('Confirm the consent before sending photos.'))
        if not data.get('plattformen'):
            self.add_error('plattformen', _('Choose at least one platform.'))
        return data
