from .forms import HoursMinutesDurationField
from .ics_export import ics_export
from .models import MediaEducationSupervisor
from .models import Project
from .models import ProjectCategory
from .models import ProjectLeader
from .models import TargetGroup
from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.utils.translation import gettext_lazy as _
from import_export import resources
from import_export.admin import ExportMixin
from import_export.fields import Field
from ok_tools.admin_base import ExportForm
from ok_tools.admin_filters import DateTimeRangeListFilter
from ok_tools.admin_base import ModelAdmin
from ok_tools.admin_base import autocomplete_filter
from ok_tools.admin_base import date_range_filter
# from rangefilter.filters import DateRangeFilter
import datetime
import logging


logger = logging.getLogger('django')


class CustomDateRangeFilter(DateTimeRangeListFilter):
    """Project date from/to (classic admin; Unfold uses its own range filter)."""

    title = _('Date')
    with_time = False


class MediaEducationSupervisorAdmin(ModelAdmin):
    """Define search_fields for ProjectAdmin autocomplete_fields."""

    search_fields = ['name']


admin.site.register(MediaEducationSupervisor, MediaEducationSupervisorAdmin)


class ProjectLeaderAdmin(ModelAdmin):
    """Define search fields for ProjectAdmin autocomplete_fields."""

    search_fields = ['name']


admin.site.register(ProjectLeader, ProjectLeaderAdmin)


class ProjectCategoryAdmin(ModelAdmin):
    """Add search_fields for the AutocompleteFilterFactory."""

    search_fields = ['name']


admin.site.register(ProjectCategory, ProjectCategoryAdmin)


class TargetGroupAdmin(ModelAdmin):
    """Add search_fields for the AutocompleteFilterFactory."""

    search_fields = ['name']


admin.site.register(TargetGroup, TargetGroupAdmin)


class ProjectResource(resources.ModelResource):
    """Define the export for Projects."""

    def _f(field, name=None):
        """Shortcut for field creation."""
        return Field(attribute=field, column_name=name)

    title = _f('title', _('Title'))
    topic = _f('topic', _('Topic'))
    description = _f('description', _('Description'))
    date = _f('date', _('Date'))
    duration = _f('duration', _('Duration'))
    external_venue = _f('external_venue', _('External venue'))
    jugendmedienschutz = _f('jugendmedienschutz', _('Jugendmedienschutz'))
    target_group = _f('target_group__name', _('Target group'))
    project_category = _f('project_category__name', _('Project category'))
    project_leader = _f('project_leader__name', _('Project leader'))
    bis_6 = _f('tn_0_bis_6', _('bis 6 Jahre'))
    bis_10 = _f('tn_7_bis_10', _('7-10 Jahre'))
    bis_14 = _f('tn_11_bis_14', _('11-14 Jahre'))
    bis_18 = _f('tn_15_bis_18', _('15-18 Jahre'))
    bis_34 = _f('tn_19_bis_34', _('19-34 Jahre'))
    bis_50 = _f('tn_35_bis_50', _('35-50 Jahre'))
    bis_65 = _f('tn_51_bis_65', _('51-65 Jahre'))
    ueber_65 = _f('tn_ueber_65', _('über 65 Jahre'))
    no_age = _f('tni_age_not_given', _('ohne Angabe'))
    female = _f('tn_female', _('weiblich'))
    male = _f('tn_male', _('männlich'))
    diverse = _f('tn_diverse', _('diverse'))
    no_gender = _f('tn_gender_not_given', _('ohne Angabe'))
    supervisors = Field()

    def dehydrate_supervisors(self, project: Project) -> str:
        """Convert all supervisors to one string."""
        return ', '.join(
            [str(x) for x in project.media_education_supervisors.all()])

    class Meta:
        """Define meta properties for the Project export."""

        model = Project
        fields = (
            'title',
            'topic',
            'description',
            'date',
            'duration',
            'external_venue',
            'jugendmedienschutz',
            'target_group',
            'project_category',
            'project_leader',
            'bis_6',
            'bis_10',
            'bis_14',
            'bis_18',
            'bis_34',
            'bis_50',
            'bis_65',
            'ueber_65',
            'no_age',
            'female',
            'male',
            'diverse',
            'no_gender',
            'supervisors',
        )
        name = _('Projects')


class YearFilter(admin.SimpleListFilter):
    """Filter after this or last year."""

    title = _('start year')

    parameter_name = 'date'

    def lookups(self, request, model_admin):
        """Define labels to filter after this or last year."""
        return (
            ('this', _('This year')),
            ('last', _('Last year')),
        )

    def queryset(self, request, queryset):
        """Filter after creation date for this or last year."""
        match self.value():
            case None:
                return
            case 'this':
                return queryset.filter(
                    date__year=datetime.datetime.now().year)
            case 'last':
                return queryset.filter(
                    date__year=datetime.datetime.now().year-1)
            case _:
                msg = f'Invalid value {self.value()}.'
                logger.error(msg)
                raise ValueError(msg)


class ProjectAdmin(ExportMixin, ModelAdmin):
    """Admin interface definitions for Projects."""

    resource_classes = [ProjectResource]
    export_form_class = ExportForm
    change_list_template = 'admin/change_list_ics_export.html'

    list_display = (
        'title',
        'topic',
        'date',
        'project_leader',
        'jugendmedienschutz',
        'democracy_project',
    )

    autocomplete_fields = [
        'project_category',
        'target_group',
        'project_leader',
        'media_education_supervisors',
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Duration as hours:minutes; keeps the widget of the admin theme."""
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'duration' and field is not None:
            field.widget.attrs.setdefault('placeholder', 'h:mm')
            field = HoursMinutesDurationField(
                required=field.required,
                label=field.label,
                widget=field.widget,
                help_text=_('Hours and minutes, e.g. 2:30'),
            )
        return field

    ordering = ('-date',)
    search_fields = ('title', 'topic', 'description')
    search_help_text = _('title, topic, description')

    list_filter = (
        autocomplete_filter(_('Target Group'), 'target_group'),
        autocomplete_filter(_('Project Category'), 'project_category'),
        autocomplete_filter(_('Project leader'), 'project_leader'),
        'jugendmedienschutz',
        'democracy_project',
        date_range_filter('date', CustomDateRangeFilter),
        YearFilter,
    )

    # PERFORMANCE OPTIMIZATION: Reduce N+1 queries in list view
    def get_queryset(self, request):
        """Optimize queryset with select_related and prefetch_related."""
        return super().get_queryset(request).select_related(
            'project_leader', 
            'project_category'
        ).prefetch_related(
            'target_group', 
            'media_education_supervisors'
        )

    fieldsets = (
        (_('Basic Information'), {
            'fields': ('title', 'topic', 'description')
        }),
        (_('Schedule & Details'), {
            'fields': (
                'date',
                'duration',
                'external_venue',
                'jugendmedienschutz',
                'democracy_project',
            )
        }),
        (_('Organization'), {
            'fields': (
                'project_category',
                'target_group',
                'project_leader',
                'media_education_supervisors',
            )
        }),
        (_('Participants by Age'), {
            'fields': (
                'tn_0_bis_6',
                'tn_7_bis_10',
                'tn_11_bis_14',
                'tn_15_bis_18',
                'tn_19_bis_34',
                'tn_35_bis_50',
                'tn_51_bis_65',
                'tn_ueber_65',
                'tn_age_not_given',
            ),
            'description': _('Enter the number of participants in each age group. Total must match gender totals.')
        }),
        (_('Participants by Gender'), {
            'fields': (
                'tn_female',
                'tn_male',
                'tn_diverse',
                'tn_gender_not_given',
            ),
            'description': _('Enter the number of participants by gender. Total must match age group totals.')
        }),
    )

    actions = ['duplicate_project']

    @admin.action(description=_('Create a copy of selected projects'))
    def duplicate_project(self, request, queryset):
        """Create a copy of selected projects."""
        count = queryset.count()
        
        for obj in queryset:
            # Save ManyToManyField data before copying
            media_education_supervisors = list(obj.media_education_supervisors.all())
            
            # Reset id to create a new instance
            obj.pk = None
            obj._state.adding = True
            
            # Save the new project
            obj.save()
            
            # Restore ManyToManyField relationships
            obj.media_education_supervisors.set(media_education_supervisors)
        
        self.message_user(
            request,
            _('%(count)d project copy was successfully created.') % {'count': count} if count == 1
            else _('%(count)d project copies were successfully created.') % {'count': count},
            messages.SUCCESS
        )

    def get_urls(self):
        """Add the ics_export_view to the admin urls."""
        return super().get_urls() + [
            path(
                'calender_export',
                self.ics_export_view,
                name='calender_export',
            )
        ]

    # CAUTION: This view is reachable without any authentication
    def ics_export_view(self, request):
        """Export project dates as ics."""
        # This method belongs to the ExportMixin and creates a queryset from
        # the urls query string.
        queryset = self.get_export_queryset(request)
        return ics_export(queryset)


admin.site.register(Project, ProjectAdmin)
