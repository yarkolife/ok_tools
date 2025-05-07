from .views import export_inventory_items
from django.urls import path


app_name = 'inventory'

urlpatterns = [
    path('export/', export_inventory_items, name='export_inventory_items'),
]
