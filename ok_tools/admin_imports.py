"""
Import custom admin configurations.
This file is imported in urls.py to ensure custom admin is loaded.
"""

# Import custom admin configurations
from .admin_custom import register_custom_admin
