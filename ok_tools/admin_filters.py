"""From/to date (and time) list filter shared by several admins.

Renders admin/filter_datetime_range.html. Used directly by the broadcast
date of the contributions and, without Unfold, by the project date.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
import datetime


class DateTimeRangeListFilter(admin.FieldListFilter):
    """Filter on ``<field>__gte_0`` (date), ``__gte_1`` (time), ``__lte_0``, ``__lte_1``.

    Set ``with_time = False`` for a DateField: only the date inputs are shown.
    """

    template = 'admin/filter_datetime_range.html'
    title = _('Date')
    with_time = True

    _SUFFIXES = ('gte_0', 'gte_1', 'lte_0', 'lte_1')

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.field_path = field_path
        self.parameter_name = field_path
        super().__init__(field, request, params, model, model_admin, field_path)
        # Django 5+ passes every query value as a list.
        self.values = {}
        for suffix in self._SUFFIXES:
            value = self.used_parameters.get(f'{field_path}__{suffix}')
            if isinstance(value, (list, tuple)):
                value = value[-1] if value else None
            self.values[suffix] = (value or '').strip()
        if not self.with_time:
            self.values['gte_1'] = self.values['lte_1'] = ''
        # Other query parameters (filters, search, ordering), kept by the
        # form and the reset link. The page number is dropped on purpose.
        own = set(self.expected_parameters())
        self.other_params = [
            (key, value)
            for key, values in request.GET.lists()
            if key not in own and key != 'p'
            for value in values
        ]

    def expected_parameters(self):
        return [f'{self.parameter_name}__{suffix}' for suffix in self._SUFFIXES]

    def has_output(self):
        return True

    def is_active(self):
        return bool(self.values['gte_0'] or self.values['lte_0'])

    def _label(self, date_key, time_key):
        try:
            text = datetime.datetime.strptime(self.values[date_key], '%Y-%m-%d').strftime('%d.%m.%Y')
        except ValueError:
            return self.values[date_key]
        return f"{text} {self.values[time_key]}".strip()

    @property
    def label_from(self):
        return self._label('gte_0', 'gte_1') if self.values['gte_0'] else ''

    @property
    def label_to(self):
        return self._label('lte_0', 'lte_1') if self.values['lte_0'] else ''

    def choices(self, changelist):
        return ({
            'query_string': changelist.get_query_string(remove=self.expected_parameters()),
            'display': self.title,
            'selected': self.is_active(),
        },)

    def _combine(self, date_str, time_str, default_time):
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        if not self.with_time:
            return date
        time = datetime.datetime.strptime(time_str, '%H:%M').time() if time_str else default_time
        return datetime.datetime.combine(date, time)

    def queryset(self, request, queryset):
        v = self.values
        if v['gte_0']:
            try:
                start = self._combine(v['gte_0'], v['gte_1'], datetime.time.min)
                queryset = queryset.filter(**{f'{self.field_path}__gte': start})
            except ValueError:
                pass
        if v['lte_0']:
            try:
                end = self._combine(v['lte_0'], v['lte_1'], datetime.time.max)
                queryset = queryset.filter(**{f'{self.field_path}__lte': end})
            except ValueError:
                pass
        return queryset
