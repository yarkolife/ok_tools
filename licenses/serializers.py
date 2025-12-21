from datetime import datetime
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers
from .models import License
from contributions.models import Contribution
from planung.models import TagesPlan


class LicenseMetadataSerializer(serializers.Serializer):
    """
    Serializer for License metadata export.
    
    Provides metadata in the format required for external video upload systems.
    """
    
    name = serializers.CharField(source='title')
    description = serializers.CharField()
    category = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    originallyPublishedAt = serializers.SerializerMethodField()
    senderResponsible = serializers.SerializerMethodField()
    videoNumber = serializers.IntegerField(source='number')
    saveToMediathek = serializers.BooleanField(source='store_in_ok_media_library')
    allowExchange = serializers.BooleanField(source='media_authority_exchange_allowed')
    youthProtectionNecessary = serializers.BooleanField(
        source='youth_protection_necessary',
        allow_null=True
    )
    youthProtectionCategory = serializers.CharField(
        source='youth_protection_category',
        allow_blank=True,
        allow_null=True
    )
    targetChannel = serializers.SerializerMethodField()
    
    def get_category(self, obj):
        """Get category name."""
        return obj.category.name if obj.category else None
    
    def get_tags(self, obj):
        """
        Get tags list (max 4 tags).
        
        Returns the tags array, limited to first 4 items if more exist.
        """
        if not obj.tags or obj.tags is None:
            return []
        tags = obj.tags if isinstance(obj.tags, list) else []
        return tags[:4]  # Maximum 4 tags
    
    def get_senderResponsible(self, obj):
        """
        Get sender responsible name from profile.
        
        Format: "FirstName LastName"
        """
        if not obj.profile:
            return ""
        first_name = obj.profile.first_name or ""
        last_name = obj.profile.last_name or ""
        return f"{first_name} {last_name}".strip()
    
    def get_originallyPublishedAt(self, obj):
        """
        Get original publication date in ISO 8601 format.
        
        Priority:
        1. Get first Contribution.broadcast_date (final data from playout import)
        2. If not found, search in planung/TagesPlan.json_plan.items by license number
        
        Returns ISO 8601 formatted datetime string or None.
        """
        # First, try to get the actual broadcast date from contributions (priority data)
        # Optimized query with only needed fields
        first_contribution = Contribution.objects.filter(
            license=obj
        ).only('broadcast_date').order_by('broadcast_date').first()
        
        if first_contribution:
            return first_contribution.broadcast_date.isoformat()
        
        # If no contribution found, fall back to TagesPlan
        # Use only_fields to reduce data transfer
        plans = TagesPlan.objects.only('datum', 'json_plan').all()
        
        for plan in plans:
            items = plan.json_plan.get('items', [])
            for item in items:
                if item.get('number') == obj.number:
                    # Found in planning, try to use the plan date + time
                    plan_date = plan.datum
                    
                    # Get start time from item
                    start_time_str = item.get('start')
                    # Only use TagesPlan time if we have a valid, non-empty start time
                    if start_time_str and start_time_str.strip():
                        try:
                            # Parse time string like "18:00" or "18:00:00"
                            time_parts = start_time_str.strip().split(':')
                            hour = int(time_parts[0])
                            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                            second = int(time_parts[2]) if len(time_parts) > 2 else 0
                            plan_time = datetime.min.time().replace(hour=hour, minute=minute, second=second)
                            
                            # Combine date and time
                            dt = datetime.combine(plan_date, plan_time)
                            # Make it timezone-aware
                            dt = timezone.make_aware(dt)
                            return dt.isoformat()
                        except (ValueError, AttributeError, IndexError):
                            # If parsing fails, continue to next plan
                            pass
        
        # No data found in either Contribution or TagesPlan
        return None
    
    def get_targetChannel(self, obj):
        """
        Get target channel for video publishing.
        
        Priority:
        1. Get targetChannel from profile.media_authority via reverse mapping
        2. Fallback to PEERTUBE_CHANNEL from settings
        
        Returns the PeerTube channel in ActivityPub/Fediverse format.
        """
        # Try to get targetChannel from profile's media_authority
        if obj.profile and obj.profile.media_authority:
            target_channel = obj.profile.media_authority.target_channel
            if target_channel:
                return target_channel
        
        # Fallback to settings
        return getattr(settings, 'PEERTUBE_CHANNEL', '')

