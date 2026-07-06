from .views import export_inventory_items
from .views import serve_item_image
from .views import serve_item_image_thumbnail
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import (
    InventoryItemViewSet, CategoryViewSet,
    LocationViewSet, OrganizationViewSet
)


# Create router and register viewsets
router = DefaultRouter()
router.register(r'items', InventoryItemViewSet, basename='inventoryitem')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'locations', LocationViewSet, basename='location')
router.register(r'organizations', OrganizationViewSet, basename='organization')

app_name = 'inventory'

urlpatterns = [
    path('export/', export_inventory_items, name='export_inventory_items'),
    path('item-image/<int:image_id>/', serve_item_image, name='item_image'),
    path('item-image/<int:image_id>/thumb/', serve_item_image_thumbnail, name='item_image_thumb'),
    path('api/', include(router.urls)),
]
