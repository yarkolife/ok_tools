from .models import License
from .models import YouthProtectionCategory
from .widgets import TagsInputWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML
from crispy_forms.layout import Field
from crispy_forms.layout import Layout
from crispy_forms.layout import Submit
from datetime import timedelta
from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _
import logging
import re


class BooleanSelectOnly(forms.Select):
    """Select widget with only Yes/No options (no Unknown) for user forms."""
    
    def __init__(self, attrs=None):
        choices = [
            ('', _('Please select')),
            ('1', _('Yes')),
            ('0', _('No')),
        ]
        super().__init__(attrs, choices=choices)
    
    def value_from_datadict(self, data, files, name):
        """Convert form value to boolean or None."""
        value = data.get(name)
        if value == '1':
            return True
        elif value == '0':
            return False
        return None
    
    def get_context(self, name, value, attrs):
        """Override to properly convert boolean values for display."""
        # Convert True/False to '1'/'0' for proper selection in the widget
        if value is True:
            value = '1'
        elif value is False:
            value = '0'
        elif value is None:
            value = ''
        return super().get_context(name, value, attrs)


logger = logging.getLogger('django')


class CreateLicenseForm(forms.ModelForm):
    """Form to create a license."""

    class Meta:
        """The okuser field is not visible for the user."""

        model = License
        exclude = ('profile', 'confirmed', 'number')
        widgets = {
            'repetitions_allowed': BooleanSelectOnly(attrs={'id': 'id_repetitions_allowed', 'required': True}),
            'store_in_ok_media_library': BooleanSelectOnly(attrs={'id': 'id_store_in_ok_media_library', 'required': True}),
            'media_authority_exchange_allowed': BooleanSelectOnly(attrs={'id': 'id_media_authority_exchange_allowed', 'required': True}),
            'media_authority_exchange_allowed_other_states': BooleanSelectOnly(attrs={'id': 'id_media_authority_exchange_allowed_other_states', 'required': True}),
            'youth_protection_necessary': BooleanSelectOnly(attrs={'id': 'id_youth_protection_necessary', 'required': True}),
            'youth_protection_category': forms.Select(attrs={'id': 'id_youth_protection_category'}),
            'duration': forms.widgets.TimeInput,
            'suggested_date': forms.DateInput(attrs={"type": "date"}),
            'further_persons': forms.Textarea(attrs={'style': 'max-height: 4em'}),
            'tags': TagsInputWidget(),
            'signature_svg': forms.HiddenInput(),
            'signature_points': forms.HiddenInput(),
            'signature_metadata': forms.HiddenInput(),
            'signature_method': forms.HiddenInput(),
            'signature_signed_at': forms.HiddenInput(),
        }

    def is_valid(self) -> bool:
        """If the LR is a screen_board, duration is not required."""
        if self.data.get('is_screen_board'):
            # it's a screen board, we are fine
            return super().is_valid()

        # Validate required boolean fields (must be Yes or No, not empty)
        boolean_fields = [
            'repetitions_allowed',
            'store_in_ok_media_library',
            'media_authority_exchange_allowed',
            'media_authority_exchange_allowed_other_states',
            'youth_protection_necessary',
        ]
        
        for field_name in boolean_fields:
            value = self.data.get(field_name)
            if not value or value == '':
                self.add_error(
                    field_name,
                    _('This field is required. Please select Yes or No.')
                )

        # Convert youth_protection to boolean
        youth_protection_value = self.data.get('youth_protection_necessary')
        youth_protection = youth_protection_value in ['true', 'True', 'Ja', True, '1'] or str(youth_protection_value) == '1'
        if youth_protection:  # If youth protection is necessary
            youth_category = self.data.get('youth_protection_category')
            if youth_category == YouthProtectionCategory.NONE:
                self.add_error(
                    'youth_protection_category',
                    _('If youth protection is necessary, you have to choose a youth protection category.')
                )

        # Validate duration format
        duration = self.data.get('duration') or ""
        hh_mm_ss = r'\d{2}:\d{2}:\d{2}'
        mm_ss = r'\d{2}:\d{2}'
        if (not re.fullmatch(hh_mm_ss, duration) and
                not re.fullmatch(mm_ss, duration)):
            # duration format is not valid
            self.add_error(
                'duration',
                _('Invalid format. Please use the format hh:mm:ss or mm:ss.')
            )
            return super().is_valid() and False  # to collect further errors

        times = duration.split(':')
        if re.fullmatch(hh_mm_ss, duration):
            datetime = timedelta(
                hours=int(times[0]),
                minutes=int(times[1]),
                seconds=int(times[2])
            )
        else:
            assert re.fullmatch(mm_ss, duration)
            datetime = timedelta(
                minutes=int(times[0]),
                seconds=int(times[1]),
            )

        if not datetime:
            # the duration format is valid but duration is 0
            self.add_error('duration', _('The duration field is required.'))
            return super().is_valid and False  # to collect further errors

        # Video upload is now handled separately after license creation
        # No validation needed here
        
        return super().is_valid()



    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Video upload is now handled separately after license creation
        # No need to add video_file field here
        
        # Make boolean fields required for user forms
        self.fields['repetitions_allowed'].required = True
        self.fields['store_in_ok_media_library'].required = True
        self.fields['media_authority_exchange_allowed'].required = True
        self.fields['media_authority_exchange_allowed_other_states'].required = True
        self.fields['youth_protection_necessary'].required = True
        
        self.helper = FormHelper()
        layout_fields = [
            'title',
            'subtitle',
            'description',
            'further_persons',
            'category',
            'tags',
            HTML(_screen_board_js()),
            Field('is_screen_board', onclick="showDuration()"),
            'is_live',
            'duration',
            'suggested_date',
            'repetitions_allowed',
            'media_authority_exchange_allowed',
            'media_authority_exchange_allowed_other_states',
            'youth_protection_necessary',
            'youth_protection_category',
            'store_in_ok_media_library',
        ]
        
        layout_fields.append(Submit('save', _('Save')))
        self.helper.layout = Layout(*layout_fields)


def _screen_board_js() -> str:
    return '''
        <script>
        function showDuration() {
            element = document.getElementById('div_id_duration')
            if (!document.getElementById("id_is_screen_board").checked){
                element.style.display = "initial"
            } else {
                element.style.display = "none"
            }
            // document.getElementById().remove()
        }
        window.onload = function(){ showDuration() }
        </script>
        <style>

            #div_id_youth_protection_category .asteriskField {
        display: none;
        }
        </style>

   '''


class RangeNumericForm(forms.Form):
    """A form for the numeric filter."""

    name = None

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        self.name = kwargs.pop('name')
        super().__init__(*args, **kwargs)

        self.fields[self.name + '_from'] = forms.FloatField(
            label='', required=False,
            widget=forms.NumberInput(attrs={'placeholder': _('From')})
        )
        self.fields[self.name + '_to'] = forms.FloatField(
            label='', required=False,
            widget=forms.NumberInput(attrs={'placeholder': _('To')})
        )


class ImportJSONForm(forms.Form):
    """Form for importing License from JSON file."""

    json_file = forms.FileField(
        label=_('JSON File'),
        help_text=_('Upload a JSON file with license data'),
        required=True,
    )


class MediathekRescanPeriodForm(forms.Form):
    """Admin form to trigger mediathek link rescan for a period."""

    date_from = forms.DateField(
        label=_('Date from'),
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    date_to = forms.DateField(
        label=_('Date to'),
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    only_store_in_ok_media_library = forms.BooleanField(
        label=_('Only licenses stored in OK media library'),
        required=False,
        initial=True,
        help_text=_('If enabled, include only licenses with “Store in OK media library” set to Yes.'),
    )

    def clean(self):
        """Validate period boundaries."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise forms.ValidationError(
                _('Date from must be earlier than or equal to Date to.')
            )

        return cleaned_data
