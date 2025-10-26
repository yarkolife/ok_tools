# Import all API endpoints from modularized files
from .users import (
    api_users_statistics,
    api_recent_users,
    api_users_detail,
)

from .statistics import (
    api_licenses_statistics,
    api_contributions_statistics,
    api_projects_statistics,
    api_filters_data,
    api_inventory_statistics,
    api_funnel_metrics,
    api_funnel_breakdown,
    api_funnel_trends,
    api_recent_licenses,
    api_system_status,
    api_quick_stats,
    api_licenses_detail,
    api_contributions_detail,
    api_projects_detail,
    api_inventory_detail,
    api_funnel_detail,
    api_media_data_statistics,
)

from .notifications import (
    api_notifications_statistics,
    api_alerts_list,
    api_alerts_resolve,
    api_notifications_detail,
    api_notifications_toggle,
    api_threshold_update,
    api_threshold_toggle,
)

# Export all functions for backward compatibility
__all__ = [
    # Users API
    'api_users_statistics',
    'api_recent_users',
    'api_users_detail',
    
    # Statistics API
    'api_licenses_statistics',
    'api_contributions_statistics',
    'api_projects_statistics',
    'api_filters_data',
    'api_inventory_statistics',
    'api_funnel_metrics',
    'api_funnel_breakdown',
    'api_funnel_trends',
    'api_recent_licenses',
    'api_system_status',
    'api_quick_stats',
    'api_licenses_detail',
    'api_contributions_detail',
    'api_projects_detail',
    'api_inventory_detail',
    'api_funnel_detail',
    'api_media_data_statistics',
    
    # Notifications API
    'api_notifications_statistics',
    'api_alerts_list',
    'api_alerts_resolve',
    'api_notifications_detail',
    'api_notifications_toggle',
    'api_threshold_update',
    'api_threshold_toggle',
]
