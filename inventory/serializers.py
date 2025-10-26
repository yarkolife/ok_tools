"""
Serializers for the inventory API.

This module defines the serializers for the inventory models that will be used
by the API to provide data to the rental application.
"""

from rest_framework import serializers
from .models import InventoryItem, Category, Location, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model."""
    
    class Meta:
        model = Organization
        fields = ['id', 'name', 'description']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location model."""
    
    class Meta:
        model = Location
        fields = ['id', 'name', 'full_path']


class InventoryItemSerializer(serializers.ModelSerializer):
    """Serializer for InventoryItem model."""
    
    owner = OrganizationSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    
    class Meta:
        model = InventoryItem
        fields = [
            'id', 'inventory_number', 'description', 'serial_number',
            'manufacturer', 'category', 'location', 'quantity', 'status',
            'owner', 'inventory_number_owner', 'purchase_date', 'purchase_cost',
            'date_added', 'available_for_rent', 'reserved_quantity', 'rented_quantity'
        ]