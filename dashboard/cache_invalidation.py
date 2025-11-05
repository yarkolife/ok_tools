"""
Cache invalidation signals for dashboard statistics.
This module provides signal handlers to invalidate cache when relevant data changes.
"""

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from contributions.models import Contribution
from licenses.models import License
from projects.models import Project
from registration.models import Profile


def invalidate_dashboard_cache():
    """Invalidate all dashboard-related cache keys."""
    # Check if we're running tests to avoid Redis connection issues
    import sys
    if 'pytest' in sys.modules or 'test' in sys.argv:
        # Skip cache invalidation during tests
        return
    
    # This is a simple approach - in production, you might want to be more selective
    # by maintaining a list of active cache keys or using cache versioning
    
    # Common cache patterns used in the dashboard
    cache_patterns = [
        'licenses_stats_',
        'contributions_stats_',
        'projects_stats_',
        'inventory_stats_',
        'funnel_metrics_',
        'quick_stats_',
        'media_data_stats_',
        'users_basic_stats_',
        'users_by_authority_',
        'users_age_groups_',
        'users_registration_trend_',
        'users_gender_distribution_',
        'users_member_distribution_',
        'users_verification_distribution_',
        'licenses_basic_stats_',
        'licenses_duration_stats_',
        'licenses_by_category_',
        'licenses_by_authority_',
        'licenses_by_gender_',
        'licenses_by_age_',
        'licenses_trend_',
        'licenses_confirmation_rate_',
        'projects_basic_stats_',
        'projects_by_category_',
        'projects_by_target_group_',
        'projects_by_leader_',
        'projects_trend_',
        'projects_participants_stats_',
        'projects_demographic_stats_',
        'projects_characteristics_',
        'contributions:',  # For contributions widget
    ]
    
    # In Redis, we can use pattern matching to delete keys
    try:
        # Try to get Redis client directly for pattern deletion
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in cache_patterns:
            # Delete all keys matching the pattern
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception) as e:
        # Fallback to simple cache clearing if redis-redis is not available
        # or if backend doesn't support this feature
        # This is less efficient but will work
        try:
            cache.clear()
        except Exception:
            # If even cache.clear() fails, just log and continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Cache invalidation failed: {e}")


@receiver(post_save, sender=License)
def invalidate_license_cache(sender, instance, **kwargs):
    """Invalidate cache when a license is created or updated."""
    invalidate_dashboard_cache()


@receiver(post_delete, sender=License)
def invalidate_license_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when a license is deleted."""
    invalidate_dashboard_cache()


@receiver(post_save, sender=Contribution)
def invalidate_contribution_cache(sender, instance, **kwargs):
    """Invalidate cache when a contribution is created or updated."""
    invalidate_dashboard_cache()


@receiver(post_delete, sender=Contribution)
def invalidate_contribution_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when a contribution is deleted."""
    invalidate_dashboard_cache()


@receiver(post_save, sender=Project)
def invalidate_project_cache(sender, instance, **kwargs):
    """Invalidate cache when a project is created or updated."""
    invalidate_dashboard_cache()


@receiver(post_delete, sender=Project)
def invalidate_project_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when a project is deleted."""
    invalidate_dashboard_cache()


@receiver(post_save, sender=Profile)
def invalidate_profile_cache(sender, instance, **kwargs):
    """Invalidate cache when a profile is created or updated."""
    # First invalidate quick stats cache for immediate updates
    invalidate_quick_stats_cache()
    # Then invalidate full dashboard cache for complete refresh
    invalidate_dashboard_cache()


@receiver(post_delete, sender=Profile)
def invalidate_profile_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when a profile is deleted."""
    invalidate_dashboard_cache()


# More selective cache invalidation functions for better performance
def invalidate_license_related_cache():
    """Invalidate only license-related cache keys."""
    license_patterns = [
        'licenses_stats_',
        'licenses_basic_stats_',
        'licenses_duration_stats_',
        'licenses_by_category_',
        'licenses_by_authority_',
        'licenses_by_gender_',
        'licenses_by_age_',
        'licenses_trend_',
        'licenses_confirmation_rate_',
        'quick_stats_',  # Quick stats include license data
    ]
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in license_patterns:
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception):
        # Fallback - clear all cache
        try:
            cache.clear()
        except Exception:
            pass


def invalidate_contribution_related_cache():
    """Invalidate only contribution-related cache keys."""
    contribution_patterns = [
        'contributions_stats_',
        'contributions:',
        'funnel_metrics_',
        'quick_stats_',  # Quick stats include contribution data
        'media_data_stats_',
    ]
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in contribution_patterns:
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception):
        # Fallback - clear all cache
        try:
            cache.clear()
        except Exception:
            pass


def invalidate_project_related_cache():
    """Invalidate only project-related cache keys."""
    project_patterns = [
        'projects_stats_',
        'projects_basic_stats_',
        'projects_by_category_',
        'projects_by_target_group_',
        'projects_by_leader_',
        'projects_trend_',
        'projects_participants_stats_',
        'projects_demographic_stats_',
        'projects_characteristics_',
    ]
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in project_patterns:
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception):
        # Fallback - clear all cache
        try:
            cache.clear()
        except Exception:
            pass


def invalidate_user_related_cache():
    """Invalidate only user-related cache keys."""
    user_patterns = [
        'users_basic_stats_',
        'users_by_authority_',
        'users_age_groups_',
        'users_registration_trend_',
        'users_gender_distribution_',
        'users_member_distribution_',
        'users_verification_distribution_',
        'quick_stats_',  # Quick stats include user data
    ]
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in user_patterns:
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception):
        # Fallback - clear all cache
        try:
            cache.clear()
        except Exception:
            pass


def invalidate_quick_stats_cache():
    """Invalidate only quick stats-related cache keys."""
    quick_stats_patterns = [
        'quick_stats_',
    ]
    
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        for pattern in quick_stats_patterns:
            keys = redis_conn.keys(f"*{pattern}*")
            if keys:
                redis_conn.delete(*keys)
    except (ImportError, NotImplementedError, AttributeError, Exception):
        # Fallback - clear all cache
        try:
            cache.clear()
        except Exception:
            pass