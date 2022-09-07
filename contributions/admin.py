from .disa_import import disa_import
from .models import Contribution
from .models import DisaImport
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.decorators import display
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext as _p


class ContributionAdmin(admin.ModelAdmin):
    """How should the Contribution be shown on the admin site."""

    list_display = (
        '__str__',
        'get_user',
        'broadcast_date',
    )
    autocomplete_fields = ['license']

    ordering = ['-broadcast_date']
    search_fields = ['license__number']

    @display(description=_('User'))
    def get_user(self, obj):
        """Return the first an last name of the contributions user."""
        return (f'{obj.license.profile.first_name}'
                f' {obj.license.profile.last_name}')


admin.site.register(Contribution, ContributionAdmin)


class DisaImportAdmin(admin.ModelAdmin):
    """How should the DISA export data and import options be shown."""

    list_display = (
        '__str__',
        'imported',
    )

    ordering = ['-file']
    actions = ['import_files']

    @admin.action(description=_('Import selected DISA exports.'))
    def import_files(self, request, queryset):
        """Import selected files."""
        imported = 0
        for i in queryset:
            if i.imported:
                continue
            else:
                disa_import(request, i.file)
                i.imported = True
                i.save()
                imported += 1

        self.message_user(request, _p(
            '%d file successfully imported.',
            '%d files successfully imported.',
            imported
        ) % imported, messages.SUCCESS)


admin.site.register(DisaImport, DisaImportAdmin)
