from .admin import InventoryResource
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse


@staff_member_required
def export_inventory_items(request):
    """Export all inventory items as an Excel file."""
    dataset = InventoryResource().export()
    response = HttpResponse(dataset.xlsx, content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="inventory_items.xlsx"'
    return response
