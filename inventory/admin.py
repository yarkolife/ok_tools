from .forms import InspectionInlineForm
from .models import AuditLog
from .models import Category
from .models import Inspection
from .models import InspectionImport
from .models import InventoryImageConfig
from .models import InventoryImport
from .models import InventoryItem
from .models import InventoryItemImage
from .models import InventorySeries
from .models import Location
from .models import Manufacturer
from .models import Organization
from .services import InventoryService
from admin_auto_filters.filters import AutocompleteFilterFactory
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin import RelatedOnlyFieldListFilter
from django.core.management import call_command
from django.db import IntegrityError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.html import format_html_join
from django.utils.translation import gettext as _


# Inline SVG shown in the admin when an item has no photos.
def no_photo_placeholder():
    """Return the translated "no photos" SVG placeholder as safe HTML."""
    return format_html(
        '<svg width="220" height="160" viewBox="0 0 220 160" '
        'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">'
        '<rect width="220" height="160" rx="8" fill="#f0f0f0" stroke="#d0d0d0"/>'
        '<g fill="none" stroke="#b0b0b0" stroke-width="3">'
        '<rect x="70" y="58" width="80" height="56" rx="6"/>'
        '<circle cx="110" cy="86" r="16"/>'
        '<path d="M86 58l8-12h32l8 12"/>'
        '</g>'
        '<text x="110" y="138" text-anchor="middle" font-family="sans-serif" '
        'font-size="13" fill="#999">{label}</text>'
        '</svg>',
        label=_('No photos'),
    )
from import_export.admin import ExportMixin
from import_export.fields import Field
from import_export.forms import ExportForm
from import_export.resources import ModelResource
from import_export.widgets import DateWidget


class InventoryResource(ModelResource):
    """Resource for InventoryItem export/import."""

    inventory_number = Field(attribute='inventory_number', column_name=_('Inventory Number'))
    description = Field(attribute='description', column_name=_('Description'))
    serial_number = Field(attribute='serial_number', column_name=_('Serial Number'))
    manufacturer = Field(attribute='manufacturer__name', column_name=_('Manufacturer'))
    category = Field(attribute='category__name', column_name=_('Category'))
    location = Field(attribute='location', column_name=_('Location'))
    quantity = Field(attribute='quantity', column_name=_('Quantity'))
    status = Field(attribute='status', column_name=_('Status'))
    owner = Field(attribute='owner__name', column_name=_('Owner'))
    inventory_number_owner = Field(attribute='inventory_number_owner', column_name=_('Inventory Number Owner'))

    purchase_date = Field(
        attribute='purchase_date',
        column_name=_('Purchase Date'),
        widget=DateWidget(format='%Y-%m-%d')
    )

    class Meta:
        """Meta options for InventoryResource."""

        model = InventoryItem
        fields = (
            'inventory_number',
            'description',
            'serial_number',
            'manufacturer',
            'category',
            'location',
            'quantity',
            'status',
            # 'object_type',
            'owner',
            'inventory_number_owner',
            'purchase_date',
            'purchase_cost'
        )


class InspectionInline(admin.TabularInline):
    """Inline admin for Inspection model."""

    model = Inspection
    form = InspectionInlineForm
    extra = 1
    fields = ("inspection_number", "target_part", "inspection_date", "result")


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin interface for Location (hierarchical)."""

    list_display = ("full_path", "parent")
    search_fields = ("name",)
    autocomplete_fields = ("parent",)
    ordering = ("parent__id", "name")


@admin.register(InventorySeries)
class InventorySeriesAdmin(admin.ModelAdmin):
    """Admin interface for InventorySeries."""

    list_display = ('prefix', 'description', 'padding', 'active')
    list_editable = ('description', 'padding', 'active')
    search_fields = ('prefix', 'description')
    list_filter = ('active',)
    ordering = ('prefix',)


@admin.register(InventoryItem)
class InventoryItemAdmin(ExportMixin, admin.ModelAdmin):
    """Admin interface for InventoryItem."""

    change_list_template = 'admin/inventory_item_change_list.html'
    resource_class = InventoryResource
    export_form_class = ExportForm

    class Media:
        """Photo links open in an overlay instead of a new tab."""

        js = ('inventory/js/photo_lightbox.js',)

    readonly_fields = ('reserved_quantity', 'rented_quantity')
    list_display = (
        'inventory_number', 'description', 'category', 'location', 'quantity',
        'status', 'owner', 'photo_preview', 'available_for_rent'
    )
    search_fields = [
        'inventory_number', 'description', 'serial_number',
        'manufacturer__name', 'category__name', 'owner__name', 'inventory_number_owner',
        'location__name',
    ]
    list_filter = [
        AutocompleteFilterFactory(_('Manufacturer'), 'manufacturer'),
        AutocompleteFilterFactory(_('Category'), 'category'),
        AutocompleteFilterFactory(_('Owner'), 'owner'),
        AutocompleteFilterFactory(_('Location'), 'location'),
        ('purchase_date', admin.DateFieldListFilter),
        'status', 'available_for_rent',
    ]
    autocomplete_fields = ('manufacturer', 'category', 'owner', 'location')
    # Newest first, so freshly added or copied items are visible right away
    # instead of sorting to the last page by inventory number. date_added is a
    # DateField, so id breaks ties between items added on the same day.
    ordering = ('-date_added', '-id')
    actions = ['copy_items_action', 'print_barcodes_action', 'rescan_photos_action']

    # Not carried over to a copy: identity, the booking counters and the status,
    # which describe the source item only. Photos are deliberately absent too -
    # they are indexed from a folder named after the inventory number, so the
    # copy gets its own once scan_inventory_images runs. Inspections belong to
    # the physical item that was inspected and are not copied either.
    COPY_EXCLUDED_FIELDS = frozenset({
        'id', 'inventory_number', 'date_added', 'status',
        'reserved_quantity', 'rented_quantity',
    })

    @admin.action(
        description=_('Copy selected inventory items'),
        permissions=['add'],
    )
    def copy_items_action(self, request, queryset):
        """Duplicate each selected item under a fresh inventory number."""
        created = []
        for item in queryset.order_by('inventory_number'):
            values = {
                field.name: getattr(item, field.name)
                for field in InventoryItem._meta.fields
                if field.name not in self.COPY_EXCLUDED_FIELDS
            }
            # Another copy may take the number between generating and saving,
            # so retry on the unique constraint rather than failing the batch.
            for _attempt in range(5):
                number = InventoryService.generate_next_inventory_number(
                    item.inventory_number)
                try:
                    with transaction.atomic():
                        InventoryItem.objects.create(
                            inventory_number=number, **values)
                except IntegrityError:
                    continue
                created.append(number)
                break
            else:
                self.message_user(
                    request,
                    _('Could not find a free inventory number for %(number)s.')
                    % {'number': item.inventory_number},
                    level=messages.ERROR,
                )

        if created:
            self.message_user(
                request,
                _('%(count)d item(s) copied: %(numbers)s. The copies are in '
                  'stock and have no reservations.') % {
                    'count': len(created),
                    'numbers': self._format_numbers(created),
                },
                level=messages.SUCCESS,
            )

    @staticmethod
    def _format_numbers(numbers, limit=10):
        """Join numbers for a message, trimming long lists to a summary."""
        if len(numbers) <= limit:
            return ', '.join(numbers)
        rest = len(numbers) - limit
        return _('%(numbers)s and %(count)d more') % {
            'numbers': ', '.join(numbers[:limit]),
            'count': rest,
        }

    def get_readonly_fields(self, request, obj=None):
        """Return readonly fields depending on item status."""
        fields = self.readonly_fields + ('photo_gallery',)
        if obj and obj.status == InventoryItem.STATUS_RENTED:
            fields = fields + ('status',)
        return fields

    fieldsets = (
        (_('Identification'), {
            'fields': ('inventory_number', 'description', 'serial_number')
        }),
        (_('Classification'), {
            'fields': ('manufacturer', 'category', 'location', 'status')
        }),
        (_('Ownership & Inventory'), {
            'fields': ('owner', 'inventory_number_owner')
        }),
        (_('Quantity & Availability'), {
            'fields': ('quantity', 'available_for_rent', 'reserved_quantity', 'rented_quantity'),
            'description': _('Reserved and rented quantities are calculated automatically.')
        }),
        (_('Purchase Information'), {
            'fields': ('purchase_date', 'purchase_cost'),
            'classes': ('collapse',),
        }),
        (_('Notes'), {
            'fields': ('notes',),
        }),
        (_('Photos'), {
            'fields': ('photo_gallery',),
            'description': _(
                'Photos are read from the mounted folder configured in '
                'Inventory Photo Settings, in a sub-folder named after the '
                'inventory number.'
            ),
        }),
    )

    inlines = [InspectionInline]

    # PERFORMANCE OPTIMIZATION: Reduce N+1 queries in list view
    def get_queryset(self, request):
        """Optimize queryset with select_related for foreign keys."""
        return super().get_queryset(request).select_related(
            'manufacturer',
            'category',
            'location',
            'owner'
        ).prefetch_related('images')

    def get_list_display(self, request):
        """Show the photo column only while photos are enabled in settings.

        When ``InventoryImageConfig.enabled`` is off, nothing scans or serves
        photos, so the column would be an empty placeholder on every row.
        """
        list_display = super().get_list_display(request)
        if InventoryImageConfig.get_config().enabled:
            return list_display
        return tuple(f for f in list_display if f != 'photo_preview')

    @admin.display(description=_('Photo'))
    def photo_preview(self, obj):
        """Render the first photo as a small thumbnail for the list view.

        Uses the prefetched ``images`` cache, so no extra query per row. The
        full-size original opens on click, like in the rental process view.
        """
        image = next(
            (img for img in obj.images.all() if img.is_available), None)
        if image is None:
            return format_html(
                '<span style="display:inline-block;width:48px;height:48px;'
                'border:1px dashed #ccc;border-radius:4px;background:#fafafa;" '
                'title="{}"></span>',
                _('No photos'),
            )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener" title="{}" '
            'data-photo-lightbox="{}" data-original-label="{}">'
            '<img src="{}" loading="lazy" alt="{}" '
            'style="width:48px;height:48px;object-fit:cover;display:block;'
            'border:1px solid #ccc;border-radius:4px;"></a>',
            reverse('inventory:item_image', args=[image.id]),
            image.filename,
            reverse('inventory:item_image_preview', args=[image.id]),
            _('Open original'),
            reverse('inventory:item_image_thumb', args=[image.id]),
            image.filename,
        )

    @admin.display(description=_('Photos'))
    def photo_gallery(self, obj):
        """Render a gallery of item photos or a placeholder if none exist."""
        if obj is None or not obj.pk:
            return _('Save the item first to see photos.')

        images = [img for img in obj.images.all() if img.is_available]
        if not images:
            return no_photo_placeholder()

        # Uniform tiles: fixed 150x150 box, thumbnail cropped to fill via
        # object-fit:cover. The lightweight thumbnail loads in the gallery; a
        # downscaled preview opens in the lightbox on click.
        thumbs = format_html_join(
            '',
            '<a href="{}" target="_blank" rel="noopener" title="{}" '
            'data-photo-lightbox="{}" data-original-label="{}" '
            'style="display:block;width:150px;height:150px;border:1px solid #ccc;'
            'border-radius:6px;overflow:hidden;background:#fafafa;">'
            '<img src="{}" loading="lazy" alt="{}" '
            'style="width:100%;height:100%;object-fit:cover;display:block;"></a>',
            (
                (
                    reverse('inventory:item_image', args=[img.id]),
                    img.filename,
                    reverse('inventory:item_image_preview', args=[img.id]),
                    _('Open original'),
                    reverse('inventory:item_image_thumb', args=[img.id]),
                    img.filename,
                )
                for img in images
            ),
        )
        return format_html(
            '<div style="display:flex;flex-wrap:wrap;gap:10px;">{}</div>',
            thumbs,
        )

    @admin.action(description=_('Rescan photos from mounted folder'))
    def rescan_photos_action(self, request, queryset):
        """Rescan the configured photos folder and reindex all images."""
        try:
            call_command('scan_inventory_images')
            self.message_user(request, _('Photo rescan complete.'))
        except Exception as e:
            self.message_user(
                request, f'Photo rescan failed: {e}', level=messages.ERROR)

    def get_form(self, request, obj=None, **kwargs):
        """Customize form fields for InventoryItem."""
        form = super().get_form(request, obj, **kwargs)
        if 'status' in form.base_fields:
            if not (obj and obj.status == InventoryItem.STATUS_RENTED):
                original_choices = form.base_fields['status'].choices
                form.base_fields['status'].choices = [
                    choice for choice in original_choices if choice[0] != InventoryItem.STATUS_RENTED
                ]
        return form

    def print_barcodes_action(self, request, queryset):
        ids = ','.join(str(obj.id) for obj in queryset)
        try:
            url = reverse('rental:barcode_print') + f'?ids={ids}'
        except Exception:
            url = f'/rental/barcode/print/?ids={ids}'
        
        from django.template.response import TemplateResponse
        return TemplateResponse(request, 'admin/inventory/barcode_modal.html', {
            'barcode_url': url,
            'items_count': queryset.count()
        })

    print_barcodes_action.short_description = _('Barcodes drucken')


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    """Admin interface for Manufacturer."""

    list_display = ('name', 'description')
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category."""

    list_display = ('name', 'description')
    search_fields = ['name', 'description']
    ordering = ['name']


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin interface for Organization."""

    list_display = ('name', 'description')
    search_fields = ['name', 'description']
    ordering = ['name']


class AuditLogResource(ModelResource):
    """Resource for AuditLog export/import."""

    model_name = Field(attribute='model_name', column_name=_('Model Name'))
    object_id = Field(attribute='object_id', column_name=_('Object ID'))
    action = Field(attribute='action', column_name=_('Action'))
    changes = Field(attribute='changes', column_name=_('Changes'))
    timestamp = Field(attribute='timestamp', column_name=_('Timestamp'))

    class Meta:
        """Meta options for AuditLogResource."""

        model = AuditLog
        fields = (
            'model_name',
            'object_id',
            'action',
            'changes',
            'timestamp',
        )


@admin.register(AuditLog)
class AuditLogAdmin(ExportMixin, admin.ModelAdmin):
    """Admin interface for AuditLog."""

    resource_class = AuditLogResource
    export_form_class = ExportForm
    list_display = (
        'get_inventory_number',
        'action',
        'get_changes_display',
        'user',
        'timestamp'
    )
    list_filter = (
        'action',
        ('user', RelatedOnlyFieldListFilter),
    )
    search_fields = ('object_id', 'changes')
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    list_per_page = 500
    show_full_result_count = False

    # PERFORMANCE NOTE: get_inventory_number calls obj.get_inventory_number() 
    # which does a SQL query per row. Consider implementing caching if this becomes slow.
    
    def get_inventory_number(self, obj):
        """Return inventory number for AuditLog."""
        return obj.get_inventory_number()
    get_inventory_number.short_description = _('Inventory Number')
    get_inventory_number.admin_order_field = 'object_id'

    def get_changes_display(self, obj):
        """Return changes display for AuditLog."""
        return obj.get_changes_display()
    get_changes_display.short_description = _('Changes')


@admin.register(InventoryImport)
class InventoryImportAdmin(admin.ModelAdmin):
    """Admin interface for InventoryImport."""

    change_form_template = 'admin/inventory_import_change_form.html'
    list_display = ('__str__', 'import_status', 'celery_status', 'task_id', 'items_created', 'items_skipped', 'import_date', 'completed_date')
    readonly_fields = (
        'import_status',
        'celery_status',
        'task_id',
        'items_created',
        'items_skipped',
        'get_error_log_display',
        'import_date',
        'completed_date'
    )
    exclude = ('error_log_file', 'error_log')
    ordering = ['-import_date']
    actions = ['import_files']

    def get_import_status_display(self, obj):
        """Return import status with icon."""
        status_icons = {
            'pending': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
            'in_progress': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>',
            'completed': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            'completed_with_errors': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            'failed': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
        }
        return f"{status_icons.get(obj.import_status, '')} {obj.get_import_status_display()}"
    get_import_status_display.short_description = _('Status')

    def get_error_log_display(self, obj):
        """Return error log as HTML list with download link."""
        if not obj.error_log:
            return _('-')
        errors = obj.error_log.split('\n')
        error_list = format_html_join('', '<li>{}</li>', ((error,) for error in errors))
        download_link = ''
        if obj.error_log_file:
            download_link = format_html(
                '<div style="margin-top: 10px;"><a href="{}" class="button" target="_blank">{}</a></div>',
                obj.error_log_file.url,
                _('Download Error Log File')
            )
        return format_html(
            '<div style="max-height: 300px; overflow-y: auto; '
            'border: 1px solid #ccc; background: #fafafa; padding: 8px;">'
            '<ul style="margin:0; padding-left:20px;">{}</ul></div>{}',
            error_list,
            download_link
        )
    get_error_log_display.short_description = _('Error Log')

    @admin.action(description=_('Import selected inventory files'))
    def import_files(self, request, queryset):
        """Import selected inventory files."""
        for import_obj in queryset:
            try:
                # Start asynchronous import using Celery
                task_id = import_obj.import_data_async()
                
                # Show message that task has been started
                self.message_user(
                    request,
                    _('Import task for %(file)s has been started. Task ID: %(task_id)s') % {
                        'file': import_obj.file.name,
                        'task_id': task_id
                    }
                )
            except Exception as e:
                self.message_user(request, f'Error starting import for {import_obj.file.name}: {str(e)}', level=messages.ERROR)
    
    @admin.action(description=_('Import selected inventory files synchronously'))
    def import_files_sync(self, request, queryset):
        """Import selected inventory files synchronously (for backwards compatibility)."""
        inventory_service = InventoryService()
        for import_obj in queryset:
            try:
                result = inventory_service.import_inventory_data(request, import_obj.file, import_obj)
                # Update import object with results
                import_obj.items_created = result.get('created', 0)
                import_obj.items_skipped = result.get('skipped', 0)
                import_obj.error_log = result.get('error_log', '')
                import_obj.import_status = 'completed' if result.get('created', 0) > 0 else 'completed_with_errors'
                import_obj.completed_date = timezone.now()
                import_obj.save()
                
                # Show success message
                self.message_user(
                    request,
                    _('Successfully imported %(created)s items. %(skipped)s items skipped.') % {
                        'created': result.get('created', 0),
                        'skipped': result.get('skipped', 0)
                    }
                )
            except Exception as e:
                self.message_user(request, f'Error importing {import_obj.file.name}: {str(e)}', level=messages.ERROR)


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    """Admin interface for Inspection model."""

    list_display = ("inspection_number", "inventory_item", "target_part", "inspection_date", "result")
    search_fields = ("inspection_number", "inventory_item__inventory_number")
    list_filter = ("target_part",)


@admin.register(InspectionImport)
class InspectionImportAdmin(admin.ModelAdmin):
    """Admin interface for InspectionImport."""

    change_form_template = 'admin/inspection_import_change_form.html'
    list_display = ('__str__', 'import_status', 'items_created', 'items_skipped', 'import_date', 'completed_date')
    readonly_fields = (
        'import_status',
        'items_created',
        'items_skipped',
        'get_error_log_display',
        'import_date',
        'completed_date'
    )
    exclude = ('error_log_file', 'error_log')
    ordering = ['-import_date']
    actions = ['import_files']

    def get_import_status_display(self, obj):
        """Return import status with icon."""
        status_icons = {
            'pending': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>',
            'in_progress': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>',
            'completed': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><polyline points="20 6 9 17 4 12"></polyline></svg>',
            'completed_with_errors': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            'failed': '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: text-bottom;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
        }
        return f"{status_icons.get(obj.import_status, '')} {obj.get_import_status_display()}"
    get_import_status_display.short_description = _('Status')

    def get_error_log_display(self, obj):
        """Return error log as HTML list with download link."""
        if not obj.error_log:
            return _('-')
        errors = obj.error_log.split('\n')
        error_list = format_html_join('', '<li>{}</li>', ((error,) for error in errors))
        download_link = ''
        if obj.error_log_file:
            download_link = format_html(
                '<div style="margin-top: 10px;"><a href="{}" class="button" target="_blank">{}</a></div>',
                obj.error_log_file.url,
                _('Download Error Log File')
            )
        return format_html(
            '<div style="max-height: 300px; overflow-y: auto; '
            'border: 1px solid #ccc; background: #fafafa; padding: 8px;">'
            '<ul style="margin:0; padding-left:20px;">{}</ul></div>{}',
            error_list,
            download_link
        )
    get_error_log_display.short_description = _('Error Log')

    @admin.action(description=_('Import selected inspection files'))
    def import_files(self, request, queryset):
        """Import selected inspection files."""
        inventory_service = InventoryService()
        for import_obj in queryset:
            try:
                result = inventory_service.import_inspection_data(request, import_obj.file, import_obj)
                # Update import object with results
                import_obj.items_created = result.get('created', 0)
                import_obj.items_skipped = result.get('skipped', 0)
                import_obj.error_log = result.get('error_log', '')
                import_obj.import_status = 'completed' if result.get('created', 0) > 0 else 'completed_with_errors'
                import_obj.completed_date = timezone.now()
                import_obj.save()
                
                # Show success message
                self.message_user(
                    request,
                    _('Successfully imported %(created)s inspections. %(skipped)s items skipped.') % {
                        'created': result.get('created', 0),
                        'skipped': result.get('skipped', 0)
                    }
                )
            except Exception as e:
                self.message_user(request, f'Error importing {import_obj.file.name}: {str(e)}', level=messages.ERROR)


class InventoryImageConfigForm(forms.ModelForm):
    """Config form that offers a dropdown of media_files storage locations."""

    class Meta:
        """Meta options for InventoryImageConfigForm."""

        model = InventoryImageConfig
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Replace the raw id field with a labelled dropdown when possible."""
        super().__init__(*args, **kwargs)
        from django.apps import apps
        if not apps.is_installed('media_files'):
            # media_files is disabled; hide the reference field entirely.
            self.fields.pop('media_storage_location_id', None)
            return
        StorageLocation = apps.get_model('media_files', 'StorageLocation')
        choices = [('', '---------')] + [
            (s.id, f'{s.name} — {s.path}')
            for s in StorageLocation.objects.filter(is_active=True)
        ]
        self.fields['media_storage_location_id'] = forms.TypedChoiceField(
            choices=choices,
            coerce=int,
            empty_value=None,
            required=False,
            label=self.fields['media_storage_location_id'].label,
            help_text=self.fields['media_storage_location_id'].help_text,
        )


@admin.register(InventoryImageConfig)
class InventoryImageConfigAdmin(admin.ModelAdmin):
    """Singleton admin for inventory photo settings."""

    form = InventoryImageConfigForm
    fields = (
        'enabled',
        'media_storage_location_id',
        'base_path',
        'supported_formats',
        'thumbnails_beside_originals',
        'resolved_folder',
    )
    readonly_fields = ('resolved_folder',)

    def get_fields(self, request, obj=None):
        """Hide the storage-location field when media_files is disabled."""
        fields = list(super().get_fields(request, obj))
        from django.apps import apps
        if not apps.is_installed('media_files'):
            fields = [f for f in fields if f != 'media_storage_location_id']
        return fields

    def has_add_permission(self, request):
        """Only one config instance allowed."""
        return not InventoryImageConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the config."""
        return False

    @admin.display(description=_('Resolved photos folder'))
    def resolved_folder(self, obj):
        """Show the effective base directory and whether it exists."""
        if obj is None or not obj.pk:
            return _('Save to resolve the folder.')
        base_dir = obj.get_base_dir()
        if base_dir is None:
            return format_html(
                '<span style="color:#c00;">{}</span>',
                _('Not configured or directory does not exist.')
            )
        return format_html('<code>{}</code>', str(base_dir))


@admin.register(InventoryItemImage)
class InventoryItemImageAdmin(admin.ModelAdmin):
    """Admin interface for indexed inventory item photos."""

    list_display = (
        'filename', 'item', 'is_available', 'file_size', 'last_scanned')
    list_filter = ('is_available',)
    search_fields = (
        'filename', 'relative_path', 'item__inventory_number')
    readonly_fields = (
        'item', 'filename', 'relative_path', 'file_size',
        'is_available', 'last_scanned', 'created_at')
    ordering = ('item', 'filename')

    def has_add_permission(self, request):
        """Records are created by the scan, not manually."""
        return False
