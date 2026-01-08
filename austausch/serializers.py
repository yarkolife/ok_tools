"""Serializers for Austausch API endpoints."""

from rest_framework import serializers
from .models import ExchangeItem, ExchangeImport


class ExchangeItemSerializer(serializers.ModelSerializer):
    """Serializer for ExchangeItem."""
    
    channel_display = serializers.CharField(source='channel', read_only=True)
    import_status_display = serializers.CharField(source='get_import_status_display', read_only=True)
    is_oktools_managed_display = serializers.BooleanField(source='is_oktools_managed', read_only=True)
    
    class Meta:
        model = ExchangeItem
        fields = [
            'id',
            'contribution_id',
            'filename',
            'file_path',
            'channel',
            'channel_display',
            'file_size',
            'file_type',
            'title',
            'description',
            'duration',
            'sendeverantwortung',
            'is_oktools_managed',
            'is_oktools_managed_display',
            'is_legacy',
            'import_status',
            'import_status_display',
            'discovered_at',
            'last_seen_at',
            'imported_at',
            'imported_license_id',
        ]
        read_only_fields = [
            'id',
            'discovered_at',
            'last_seen_at',
            'imported_at',
        ]


class ExchangeImportSerializer(serializers.ModelSerializer):
    """Serializer for ExchangeImport."""
    
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    exchange_item = ExchangeItemSerializer(read_only=True)
    
    class Meta:
        model = ExchangeImport
        fields = [
            'id',
            'exchange_item',
            'imported_by_id',
            'status',
            'status_display',
            'error_message',
            'created_at',
            'completed_at',
            'license_id',
            'video_file_id',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'completed_at',
        ]

