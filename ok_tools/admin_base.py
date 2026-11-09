"""
Base classes and filter helpers for ModelAdmins.

With ADMIN_UNFOLD_ENABLED they resolve to Unfold's styled classes and
filters, otherwise to the stock Django ones and the filter packages the
classic admin uses. Admins that import from here look right in both modes,
so the admin can move to Unfold one app at a time while the flag is off.
"""

from django.conf import settings


UNFOLD = bool(getattr(settings, "ADMIN_UNFOLD_ENABLED", False))


def _parse_date(value):
    """ISO date or a date in the active locale's input formats."""
    from django.utils import dateparse
    from django.utils import formats
    import datetime
    value = value.strip()
    try:
        parsed = dateparse.parse_date(value)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed
    for fmt in formats.get_format("DATE_INPUT_FORMATS"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except (TypeError, ValueError):
            continue
    return None


def _parse_datetime(date_value, time_value, end_of_day=False):
    """Combine a date and an optional time (HH:MM[:SS]) to an aware datetime."""
    from django.utils import dateparse
    from django.utils import timezone
    import datetime
    day = _parse_date(date_value)
    if day is None:
        return None
    try:
        moment = dateparse.parse_time(time_value.strip()) if time_value.strip() else None
    except ValueError:
        moment = None
    if moment is None:
        moment = datetime.time.max if end_of_day else datetime.time.min
    value = datetime.datetime.combine(day, moment)
    return timezone.make_aware(value) if settings.USE_TZ else value

if UNFOLD:
    from unfold.admin import ModelAdmin as _UnfoldModelAdmin
    from unfold.admin import StackedInline  # noqa: F401
    from unfold.admin import TabularInline  # noqa: F401
    from unfold.contrib.filters.admin import AutocompleteSelectFilter
    from unfold.contrib.filters.admin import RangeDateFilter
    from unfold.contrib.filters.admin import RangeDateTimeFilter
    from unfold.contrib.import_export.forms import ExportForm  # noqa: F401
    from unfold.contrib.import_export.forms import ImportForm  # noqa: F401
    from unfold.forms import AdminPasswordChangeForm  # noqa: F401
    from unfold.widgets import INPUT_CLASSES
    from django.db.models import DateTimeField

    # CSS classes for inputs of our own filter forms.
    FILTER_INPUT_CLASS = " ".join(INPUT_CLASSES)
    # Template for our own from/to number filters (fields <name>_from/_to).
    NUMERIC_RANGE_FILTER_TEMPLATE = "unfold/filters/filters_numeric_range.html"

    class ModelAdmin(_UnfoldModelAdmin):
        # Range and autocomplete filters only apply with a submit button.
        list_filter_submit = True

    class RangeDateFilter(RangeDateFilter):  # noqa: F811
        """Unfold's date range filter with working date parsing.

        Unfold parses with settings.DATE_INPUT_FORMATS, which is a single
        string here (it is also used for strftime), so no date was ever
        recognised and the filter did nothing. Dates are read as ISO or in
        the active locale's input formats; on a datetime field the range
        compares whole days, so "to" includes the last day.
        """

        def queryset(self, request, queryset):
            lookup = self.parameter_name
            if isinstance(self.field, DateTimeField):
                lookup += "__date"
            filters = {}
            for suffix, operator in (("_from", "gte"), ("_to", "lte")):
                value = self.used_parameters.get(self.parameter_name + suffix)
                if isinstance(value, str) and value:
                    parsed = _parse_date(value)
                    if parsed is not None:
                        filters[f"{lookup}__{operator}"] = parsed
            return queryset.filter(**filters)

    class RangeDateTimeFilter(RangeDateTimeFilter):  # noqa: F811
        """Unfold's date-and-time range filter with working parsing."""

        def queryset(self, request, queryset):
            filters = {}
            for suffix, operator in (("_from", "gte"), ("_to", "lte")):
                date_value = self.used_parameters.get(f"{self.parameter_name}{suffix}_0")
                time_value = self.used_parameters.get(f"{self.parameter_name}{suffix}_1")
                if isinstance(date_value, str) and date_value:
                    parsed = _parse_datetime(date_value, time_value or "",
                                             end_of_day=operator == "lte")
                    if parsed is not None:
                        filters[f"{self.parameter_name}__{operator}"] = parsed
            return queryset.filter(**filters)

else:
    from django.contrib.admin import ModelAdmin  # noqa: F401
    from django.contrib.admin import StackedInline  # noqa: F401
    from django.contrib.admin import TabularInline  # noqa: F401
    from django.contrib.auth.forms import AdminPasswordChangeForm  # noqa: F401
    from import_export.forms import ExportForm  # noqa: F401
    from import_export.forms import ImportForm  # noqa: F401

    FILTER_INPUT_CLASS = ""
    NUMERIC_RANGE_FILTER_TEMPLATE = "admin/filter_numeric_range.html"


def autocomplete_filter(title, field_path):
    """A related-field filter with a search box."""
    if UNFOLD:
        return (field_path, AutocompleteSelectFilter)
    from admin_auto_filters.filters import AutocompleteFilterFactory
    return AutocompleteFilterFactory(title, field_path)


def date_range_filter(field_path, classic_filter):
    """A from/to date filter; ``classic_filter`` is used without Unfold."""
    return (field_path, RangeDateFilter if UNFOLD else classic_filter)


def datetime_range_filter(field_path, classic_filter):
    """A from/to date-and-time filter; ``classic_filter`` without Unfold."""
    return (field_path, RangeDateTimeFilter if UNFOLD else classic_filter)
