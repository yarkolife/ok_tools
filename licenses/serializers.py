from datetime import datetime
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers
from .models import License

# Optional imports for modules that may be disabled
try:
    from contributions.models import Contribution
except (ImportError, RuntimeError, ModuleNotFoundError):
    Contribution = None

try:
    from planung.models import TagesPlan
except (ImportError, RuntimeError, ModuleNotFoundError):
    TagesPlan = None


class LicenseMetadataSerializer(serializers.Serializer):
    """
    Serializer for License metadata export.
    
    Provides metadata in the format required for external video upload systems.
    """
    
    name = serializers.CharField(source='title')
    subtitle = serializers.CharField(allow_blank=True, allow_null=True)
    description = serializers.CharField()
    category = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    originallyPublishedAt = serializers.SerializerMethodField()
    senderResponsible = serializers.SerializerMethodField()
    videoNumber = serializers.IntegerField(source='number')
    saveToMediathek = serializers.BooleanField(source='store_in_ok_media_library')
    allowExchange = serializers.SerializerMethodField()
    allowExchangeOtherStates = serializers.SerializerMethodField()
    bundesland = serializers.SerializerMethodField()
    bundesland_code = serializers.SerializerMethodField()
    furtherInvolvedPersons = serializers.CharField(
        source='further_persons',
        allow_blank=True,
        allow_null=True
    )
    furtherPersons = serializers.CharField(
        source='further_persons',
        allow_blank=True,
        allow_null=True
    )
    duration = serializers.SerializerMethodField()
    repetitionsAllowed = serializers.BooleanField(
        source='repetitions_allowed',
        allow_null=True
    )
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

    def get_duration(self, obj):
        """
        Get duration as HH:MM:SS string (or MM:SS when hours are 0).
        """
        if not obj.duration:
            return None
        total = int(obj.duration.total_seconds())
        if total < 0:
            return None
        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60
        if hours > 0:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:d}:{seconds:02d}"

    def get_allowExchange(self, obj):
        return bool(obj.media_authority_exchange_allowed)

    def get_allowExchangeOtherStates(self, obj):
        return bool(obj.media_authority_exchange_allowed_other_states)

    def get_bundesland(self, obj):
        from registration.models import OrganizationConfig
        return OrganizationConfig.get_config().bundesland

    def get_bundesland_code(self, obj):
        from registration.models import OrganizationConfig
        return OrganizationConfig.get_config().bundesland_code

    def get_profile(self, obj):
        """Get profile display name from profile."""
        return self.get_senderResponsible(obj)
    
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
        if Contribution is not None:
            first_contribution = Contribution.objects.filter(
                license=obj
            ).only('broadcast_date').order_by('broadcast_date').first()
            
            if first_contribution:
                return first_contribution.broadcast_date.isoformat()
        
        # If no contribution found, fall back to TagesPlan
        # Use only_fields to reduce data transfer
        if TagesPlan is not None:
            # Ordered so that the earliest planned broadcast wins when the
            # license appears in more than one plan.
            plans = TagesPlan.objects.only('datum', 'json_plan').order_by('datum')
            
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
