from .admin import InventoryResource
from .services import InventoryService
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse


@staff_member_required
def export_inventory_items(request):
    """Export all inventory items as an Excel file."""
    inventory_service = InventoryService()
    dataset = inventory_service.export_inventory_items()
    response = HttpResponse(dataset.xlsx, content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="inventory_items.xlsx"'
    return response
