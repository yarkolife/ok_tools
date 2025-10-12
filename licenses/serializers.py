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
        1. Search in planung/TagesPlan.json_plan.items by license number
        2. If not found, get first Contribution.broadcast_date
        
        Returns ISO 8601 formatted datetime string or None.
        """
        # Try to find in TagesPlan first (optimized query)
        # Use only_fields to reduce data transfer
        plans = TagesPlan.objects.only('datum', 'json_plan').all()
        
        for plan in plans:
            items = plan.json_plan.get('items', [])
            for item in items:
                if item.get('number') == obj.number:
                    # Found in planning, use the plan date + time
                    plan_date = plan.datum
                    
                    # Get start time from item
                    start_time_str = item.get('start', '00:00')
                    if start_time_str:
                        try:
                            # Parse time string like "18:00"
                            hour, minute = map(int, start_time_str.split(':'))
                            plan_time = datetime.min.time().replace(hour=hour, minute=minute)
                        except (ValueError, AttributeError):
                            # If parsing fails, use midnight
                            plan_time = datetime.min.time()
                    else:
                        plan_time = datetime.min.time()
                    
                    # Combine date and time
                    dt = datetime.combine(plan_date, plan_time)
                    # Make it timezone-aware
                    dt = timezone.make_aware(dt)
                    return dt.isoformat()
        
        # If not found in planning, try to get first contribution
        # Optimized query with only needed fields
        first_contribution = Contribution.objects.filter(
            license=obj
        ).only('broadcast_date').order_by('broadcast_date').first()
        
        if first_contribution:
            return first_contribution.broadcast_date.isoformat()
        
        return None
    
    def get_targetChannel(self, obj):
        """
        Get target channel for video publishing.
        
        Returns the PeerTube channel from settings in ActivityPub/Fediverse format.
        """
        return getattr(settings, 'PEERTUBE_CHANNEL', '')

