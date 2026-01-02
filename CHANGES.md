CHANGELOG
=========

2026-01-02 (Version 3.2.3)
==========================

* **Video Storage Automation Enhancements**
  * **Default Playout Storage Selection**: Added intelligent selection of default playout storage for main broadcasts
    * Configurable via `VIDEO_DEFAULT_PLAYOUT_STORAGE_NAME` or `VIDEO_DEFAULT_PLAYOUT_STORAGE_PATH`
    * Auto-detects storage containing "000_Sendungen" in path or "Sendungen" in name
    * Falls back to first available PLAYOUT storage if nothing matches
    * Ensures videos are copied to correct playout location (main broadcasts vs. previews/trailers)
  * **Automatic Deletion from CUSTOM Storage**: Added automatic cleanup of CUSTOM storage after successful copy
    * Videos are moved (deleted from CUSTOM) after successful copy to archive and playout
    * Only deletes if source was CUSTOM and all required copies succeeded
    * Prevents duplicate records and keeps CUSTOM storage (entry point) clean
    * Configurable via `VIDEO_AUTO_DELETE_FROM_CUSTOM` setting (default: true)
    * Creates FileOperation records for deletion tracking
    * Updates all database records properly during copy and delete operations
  * **Enhanced Database Record Management**: Improved database record updates during video operations
    * All metadata is copied when creating new VideoFile records
    * FileOperation records are properly linked to new video records
    * Deletion operations are fully tracked in FileOperation table
    * Better logging for all database operations

2026-01-02 (Version 3.2.2)
==========================

* **Video Storage Automation and Archive Protection**
  * **Automatic Video Copying During Planning**: Added automatic video file copying when saving broadcast plans
    * Videos are automatically copied to archive and playout storage when plan is saved (not draft)
    * Smart source selection: prefers CUSTOM storage if file is recent (within configured days), otherwise uses ARCHIVE
    * Supports weekly folder organization (YYYY_KW_WW format) in playout storage
    * Configurable via environment variables for different installation types
    * Comprehensive logging and error handling
  * **Archive Storage Protection**: Added protection against accidental deletion of archive videos
    * Videos in ARCHIVE storage can be read and copied, but deletion is disabled in admin interface
    * Protection can be enabled/disabled via `VIDEO_ARCHIVE_PROTECTED` setting
    * Works for both single and bulk deletion operations
    * Prevents data loss while allowing read and copy operations
  * **Smart Source Selection**: Intelligent video source selection for copying operations
    * Prefers CUSTOM storage if file was updated within configured days (default: 7 days)
    * Falls back to ARCHIVE storage for older files
    * Excludes PLAYOUT storage from source selection to avoid circular copying
    * Configurable via `VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS` setting
  * **Configuration via Environment Variables**: Added 6 new settings for flexible configuration
    * `VIDEO_AUTO_COPY_ON_SCHEDULE`: Enable automatic copying when saving plans
    * `VIDEO_AUTO_COPY_TO_ARCHIVE`: Copy videos to archive storage automatically
    * `VIDEO_AUTO_COPY_TO_PLAYOUT`: Copy videos to playout storage automatically
    * `VIDEO_USE_WEEKLY_FOLDERS`: Use weekly folders (YYYY_KW_WW) in playout storage
    * `VIDEO_ARCHIVE_PROTECTED`: Protect archive from deletion (default: true)
    * `VIDEO_SOURCE_PREFERENCE_CUSTOM_DAYS`: Days to consider CUSTOM files as recent (default: 7)
    * All settings default to safe values (disabled) for backward compatibility
  * **Celery Task Integration**: New Celery task `copy_videos_for_plan` for asynchronous video copying
    * Runs automatically when plan is saved (if enabled)
    * Can run synchronously if Celery is not available
    * Returns detailed results for user notifications
    * Handles errors gracefully with comprehensive logging
  * **Documentation Updates**: Added comprehensive documentation for new features
    * New section in ENV_VARIABLES.md for video storage automation configuration
    * Examples for different installation types (with/without archive)
    * Configuration examples for full automation vs. disabled mode

2026-01-02 (Version 3.2.1)
==========================

* **Celery Configuration Improvements**
  * **Configurable Task Time Limits**: Added support for configuring Celery task time limits via environment variables
    * `CELERY_TASK_TIME_LIMIT` and `CELERY_TASK_SOFT_TIME_LIMIT` can now be set in `.env` files
    * Default values remain 30 minutes (hard limit) and 25 minutes (soft limit)
    * Recommended values for large video rendering: 60-120 minutes
    * Updated all configuration templates (okmq, ok-nrw, ok-bayern) with recommended values
  * **Video Rendering**: Fixed timeout issues for long video rendering tasks by making time limits configurable

2026-01-02 (Version 3.2)
========================

* **Documentation Enhancements**
  * **Comprehensive README Update**: Significantly expanded README.rst with detailed module descriptions
    * Added detailed feature descriptions for all core applications (User Registration, License Management, Media Files, Planning Tools, Contributions, Projects, Inventory, Rental, Dashboard)
    * Documented all management commands organized by module (Media Files, Rental, Inventory, Licenses, Contributions, Registration, Dashboard)
    * Added comprehensive data import documentation (DISA, Inventory, Inspections) with format support and batch processing details
    * Documented service layer architecture (Inventory, Rental, Statistics, Notification, User services)
    * Added technical details about caching strategies, database optimization, and API performance
    * Enhanced feature descriptions with sub-features and capabilities for each module
  * **Module Documentation**: Complete feature breakdown for each application
    * User Registration: Email-based authentication, GDPR compliance, profile management, print registration forms
    * License Management: Nextcloud integration, video upload, metadata export, planning system integration
    * Media Files: Multiple storage locations, video rendering with presets, checksum calculation, automatic scanning
    * Planning Tools: Daily broadcast plans (TagesPlan), calendar weeks, time extraction, JSON-based storage
    * Contributions: DISA import (XLSX/XLS), primary/repetition detection, statistics, grouped display
    * Projects: ICS export, categories, target groups, demographics, project leaders
    * Inventory: Hierarchical locations, batch imports (500 items), inspection import, audit logging
    * Rental: Equipment sets, room rentals, transactions, API endpoints, availability checking
    * Dashboard: Multiple widgets, funnel metrics, alert system, real-time updates

* **Management Commands Documentation**
  * Documented all available management commands organized by module:
    * **Media Files**: auto_scan, scan_video_storage, update_video_metadata, link_orphan_licenses, sync_licenses_videos, copy_to_playout, cleanup_playout, cleanup_missing_files, cleanup_old_file_operations, find_duplicates, cleanup_duplicates
    * **Rental**: expire_room_rentals, fix_quantity_issued, fix_missing_issue_transactions, test_nextcloud_calendar
    * **Inventory**: import_inspections, link_inspections, import_locations
    * **Licenses**: import_licenses_from_wp, delete_imported_licenses, cleanup_deleted_nextcloud_videos
    * **Contributions**: export_mediathek_report
    * **Registration**: setup_organizations
    * **Dashboard**: check_alerts
  * Noted that many commands can be run from admin interface via System Management page (requires staff access)

* **Data Import Documentation**
  * **DISA Import**: Documented Excel import (XLSX/XLS) with automatic format conversion, date-based filtering, batch processing, AJAX date extraction, and validation
  * **Inventory Import**: Documented Excel import with batch processing (500 items per batch), automatic entity creation (manufacturers, categories, locations, organizations), inventory number validation (OK-XXXX format), location hierarchy creation, error logging, and status tracking
  * **Inspection Import**: Documented CSV/XLSX import with automatic date parsing from various formats, linking to inventory items by inspection number, batch processing, and error handling

* **Technical Architecture Documentation**
  * **Service Layer**: Documented service layer architecture with Inventory, Rental, Statistics, Notification, and User services for better testability and maintainability
  * **Caching Strategy**: Documented Redis-based caching with pattern-based cache key management, cache invalidation on data changes via signals, and cache versioning support
  * **Database Optimization**: Documented batch processing for imports, optimized contribution primary/repetition detection, query optimization with select_related and prefetch_related, composite indexes, and pagination with preserved prefetch relationships
  * **API Documentation**: Enhanced REST API documentation with pagination support (default 20 items, configurable up to 200), search and filtering capabilities, and ordering support

* **Additional Features Documentation**
  * **Video Rendering**: Documented preset management (database and JSON-based), customizable intro/outro overlays, text and image overlay support, animation effects (fade, slide, zoom), position presets, template-based rendering, and preview functionality
  * **Storage Management**: Documented multiple storage location support with hierarchical tracking, UNC path support for Windows networks, automatic file scanning with scheduling, storage type classification (Archive, Playout, Custom), and file availability tracking
  * **Equipment Sets**: Documented equipment set templates, quick rental setup with equipment sets, member-created equipment sets, and template-based equipment selection
  * **Alert System**: Documented configurable alert thresholds, multiple metric types (conversion rate, absolute count, trend change), alert logging and resolution tracking, notification recipients configuration, and active/inactive threshold management

2026-01-02 (Version 3.2.0)
===========================

* **Bug Fixes and Data Integrity**
  * **Rental Quantity Fix**: Fixed critical double increment bug in `quantity_issued` calculation
    * Resolved issue where `quantity_issued` was incremented twice (once in `create_transaction()` method and once in signal handler)
    * Added management commands `fix_quantity_issued` and `fix_missing_issue_transactions` for data correction
    * Commands support dry-run mode for safe testing before applying fixes
    * Full documentation added in `deployment/docs/FIX_QUANTITY_ISSUED.md`
  * **Transaction Integrity**: Ensured all rental transactions are properly tracked and synchronized
  * **Data Migration Tools**: Added tools to fix existing data affected by the bug

* **License Management Enhancements**
  * **License Cleanup Tools**: Added management command `delete_imported_licenses` for bulk deletion of imported licenses
    * Supports deletion by date range, license number range, or profile ID
    * Includes dry-run mode for safe testing
    * Automatically handles related contributions deletion
  * **Nextcloud Integration**: Added `cleanup_deleted_nextcloud_videos` command for managing deleted videos
    * Checks Nextcloud for deleted videos and marks them as deleted in database
    * Supports configurable grace period before permanent deletion
    * Integrated as periodic Celery task for automated cleanup

* **Periodic Tasks Management**
  * **Task Setup Command**: Added `setup_periodic_tasks` management command for initializing Celery Beat tasks
    * Migrates tasks from `CELERY_BEAT_SCHEDULE` to django-celery-beat database scheduler
    * Makes tasks visible and manageable via Django admin interface
    * Supports update mode for modifying existing tasks
  * **New Periodic Tasks**: Added automated cleanup tasks
    * `cleanup_deleted_nextcloud_videos`: Periodic cleanup of deleted Nextcloud videos
    * All tasks configurable via environment variables with sensible defaults

* **Database Backup Improvements**
  * **Backup Command**: Enhanced `backup_db` management command
    * Supports compression (gzip) for space-efficient backups
    * Configurable output directory
    * Automatic backup rotation via `cleanup_old_backups` task
    * Integrated as periodic Celery task (runs daily by default)

* **Version Updates**
  * **Django**: Updated to 5.2.7 (from 5.2.5)

2025-10-25 (Version 3)
========================

* **Major Architecture Improvements**
  * **Event-Driven Architecture**: Implemented asynchronous communication between rental and inventory modules using Celery events
  * **Service Layer Pattern**: Introduced service layers for inventory and rental operations with abstract interfaces for better decoupling
  * **Microservices Preparation**: Created abstract inventory service interface to prepare for future microservices transition
  **Comprehensive Architecture Documentation**: Added complete C4 model diagrams and architectural overview in `overview.md`

* **Asynchronous Task Processing**
  * **Celery Integration**: Integrated Celery with Redis for background task processing
  * **Async Inventory Import**: Implemented asynchronous inventory import with progress tracking and error handling
  * **Background Processing**: Added Celery workers for long-running operations like imports and exports

* **API Enhancements**
  * **OpenAPI/Swagger Documentation**: Added automatic API documentation with drf-spectacular
  * **REST API for Inventory**: Implemented comprehensive REST API endpoints for inventory management
  * **Token Authentication**: Enhanced API security with token-based authentication and management interface
  * **API Rate Limiting**: Added throttling protection with 100/hour for anonymous and 1000/hour for authenticated users

* **Monitoring and Observability**
  * **Prometheus Integration**: Added comprehensive metrics collection with django-prometheus
  * **JSON Logging**: Implemented structured JSON logging for improved debugging and monitoring
  * **System Metrics**: Added metrics for HTTP requests, database operations, and model operations
  * **Performance Monitoring**: Enhanced dashboard with real-time system statistics

* **Security Enhancements**
  * **Security Headers**: Implemented comprehensive security headers (HSTS, XSS protection, etc.)
  * **CSRF Protection**: Enhanced CSRF protection with secure cookie settings
  * **Clickjacking Protection**: Added X-Frame-Options headers to prevent clickjacking attacks
 * **Vulnerability Scanning**: Integrated pip-audit for automatic dependency vulnerability scanning

* **Code Quality and Type Safety**
  * **Static Type Checking**: Added comprehensive type hints with mypy integration
  * **Code Documentation**: Added Google-style docstrings for all public APIs
  * **Unit Test Coverage**: Added 100+ unit tests for service layers with 70%+ coverage
  * **Code Quality Tools**: Integrated pre-commit hooks and automated code quality checks

* **Performance Optimizations**
  * **Bulk Import Optimization**: Optimized inventory import with bulk_create/bulk_update operations (80% faster)
  * **DISA Import Efficiency**: Improved DISA import performance with reduced database queries (~95% faster)
  * **Database Query Optimization**: Continued optimization of N+1 queries across the application
  * **Cache Improvements**: Enhanced caching strategies for better performance

* **Infrastructure Improvements**
  * **Backup Management**: Added custom management command for PostgreSQL database backups
 * **Configuration Management**: Enhanced .cfg file support for comprehensive Django configuration
  * **Deployment Scripts**: Fixed and improved deployment scripts for production environments
  * **CI/CD Integration**: Enhanced CI pipeline with code coverage and vulnerability scanning

* **Bug Fixes and Stability**
  * **Admin Interface Fixes**: Resolved CSS and display issues in Django admin interface
  * **Error Handling**: Fixed KeyError and AttributeError issues in various components
  * **Import Error Resolution**: Fixed inventory and contribution import error handling
 * **Video Player Fix**: Resolved translation-related errors in video file player

2025-10-11 (Version 2.5)
========================

* **Media Files Management Module**
  * New comprehensive module for video file management
  * Automatic file discovery and metadata extraction via ffprobe
  * Support for multiple storage locations (Archive, Playout, Custom)
  * **Auto-sync duration**: License duration automatically syncs from linked video file
    * Visual warning when durations mismatch
    * One-click sync button in admin interface
    * Automatic sync via signals when video is created/updated
  * **Video player improvements**: Fixed streaming and playback issues
    * Correct MIME-type mapping for all video formats
    * Proper range request support for seeking
    * FileResponse for efficient streaming
    * Inline content disposition (no download prompts)
 * **Duration and Tags formatting**: Improved display in admin interface
    * License duration rounded to seconds (hh:mm:ss format)
    * Tags displayed without JSON brackets and quotes
    * Empty tags show as dash (-) instead of [] or null
  * **Duration mismatch tolerance**: Smart duration comparison
    * Warning only shown if difference >= 1 second
    * Prevents false alerts for sub-second differences (e.g., 0.568s)
    * Auto-sync respects same tolerance threshold
 * **Duplicate Video Management**: Comprehensive duplicate detection and management
    * **Automatic detection**: Finds videos with same number in different storage locations
    * **Quality-based prioritization**: ARCHIVE > PLAYOUT > CUSTOM, then by bitrate/resolution
    * **Checksum verification**: Identifies identical vs different files with same number
    * **Prevention system**: Blocks copying identical files to archive storage
    * **Admin interface enhancements**:
      * Visual duplicate indicators in list view (✓ PRIMARY, ⚠️ DUPLICATE)
      * Filter by duplicate status and version type
      * Bulk actions: mark as primary, delete duplicates
      * Detailed duplicate information in change forms
      * Links between all versions of same video
      * **Management command**: `find_duplicates` with JSON output and filtering options
      * **Auto-copy improvements**: Automatically selects best quality version when copying
      * **Configuration**: New settings for storage priority and duplicate prevention
      * **Documentation**: Complete guides (DUPLICATE_MANAGEMENT.md, DUPLICATE_QUICKSTART.md)
    * **Weekly Folder Organization**: Automatic weekly folder structure for playout storage
      * **Auto-detection**: Automatically determines week from planning date (ISO 8601)
      * **Folder format**: Creates folders like `2025_KW_41` for week 41 of 2025
      * **Auto-copy integration**: Videos copied to correct weekly folder when planning saved
      * **Manual copy support**: Admin copy actions also use weekly folders
      * **Automatic creation**: Creates weekly folders if they don't exist
      * **Database integration**: VideoFile.file_path includes weekly folder path
      * **Backward compatibility**: Existing videos without weekly folders still work
      * **Documentation**: Complete guide (WEEKLY_FOLDERS.md)
    * **Advanced Automation Features**: Comprehensive automation for video file management
      * **Bidirectional sync**: Automatic linking between VideoFile and License (both directions)
      * **Mass synchronization**: `sync_licenses_videos` command for bulk linking and duration sync
      * **Automatic playout cleanup**: Move videos from playout to archive when no longer in use
      * **File attribute monitoring**: Detect when files are in use via system attributes (Windows/Linux)
      * **File lock detection**: Check if files are locked by other processes using `lsof`
      * **Auto-scan integration**: `auto_scan` command for automated storage scanning
      * **Admin actions**: "Move to archive storage" bulk action with safety checks
      * **Cron integration**: Ready for automated daily/weekly maintenance tasks
      * **Comprehensive logging**: All operations tracked in FileOperation model
      * **Admin UI improvements**:
        * **Scan button**: One-click storage scanning from admin interface
        * **Search for videos**: Button to find videos for licenses without files
        * **Bulk search**: Admin action to search videos for multiple licenses
        * **Orphan license finder**: `link_orphan_licenses` command to auto-link videos
        * **System Management**: Centralized page to run all commands from admin UI
          * Auto scan, manual scan, sync licenses, link orphans, cleanup playout, find/cleanup duplicates
          * All commands with configurable options and dry-run support
          * No terminal access required
          * Accessible via MEDIA FILES → 🎛️ System Management in admin sidebar (like planung calendar)
        * **License list enhancements**: Video status column in license admin list
          * Shows video availability status (🎬 Available, ⚠️ Not available, ❌ No video)
          * Play link (▶️ Play) for available videos that opens in popup window (800x600px)
          * Optimized queries with select_related to avoid N+1 problems
        * **Video format detection fix**: Improved MIME-type detection for video playback
          * MIME-type now determined by file extension, not ffprobe format
          * Fixes issue where renamed files (e.g., .mov → .mp4) wouldn't play
          * Videos now stream correctly instead of downloading
          * Updated metadata extraction to prioritize file extension over container format
        * **Video availability fix**: Fixed scan command to properly update video availability
          * Existing videos are now always marked as available when found during scan
          * No longer requires --force or --update-metadata flags for availability updates
          * Missing files are automatically marked as unavailable
          * Scan button in admin now works correctly for updating video status
        * **System Management fixes**: Fixed command parameter mismatches and missing functionality
          * Created missing `cleanup_duplicates` command with proper quality-based duplicate removal
          * Fixed parameter mapping for `find_duplicates` command (removed non-existent options)
          * All management commands now work correctly from System Management page
          * Added dry-run protection for destructive operations
      * **Documentation**: Complete automation guide (ADVANCED_FEATURES.md)
    * **NAS/Network Storage Support**: SMB/CIFS mounting for network shares
      * **Development (Docker/macOS)**:
        * Automatic mount scripts (mount_nas.sh, umount_nas.sh)
        * Docker volume configuration for NAS access
        * Test script for verifying access (test_nas_access.sh)
        * Full documentation: media_files/NAS_SETUP.md
      * **Production (Debian 11/gunicorn)**:
        * Automated setup script (deployment/scripts/setup-nas-debian.sh)
        * Support for multiple NAS with different IP addresses
        * fstab and systemd mount unit configurations
        * Health check and remount scripts
        * Full documentation: deployment/NAS_DEBIAN_SETUP.md
        * Quick start: deployment/PRODUCTION_NAS_QUICKSTART.txt
      * Production configs updated with [media] section (ok-bayern, ok-nrw, okmq)
    * Comprehensive video metadata: codec, bitrate, FPS, resolution, color space, chroma subsampling
    * Audio metadata: codec, bitrate, sample rate, channels, channel layout
    * Built-in video player in Django Admin with HTML5 support and seeking
    * Automatic copy from archive to playout when broadcast plans are saved
    * File integrity verification with SHA256 checksums
    * Complete operation history logging
    * Management commands: scan_video_storage, update_video_metadata, copy_to_playout, cleanup_playout
    * Admin actions: copy to playout, update metadata, verify integrity
    * Integration with License model (one-to-one relationship by number)
    * Integration with Planung module for auto-copying videos
    * Configurable via config file (docker.cfg)
    * Supported formats: mp4, mov, mpeg, mpg (configurable)
    * Full documentation:
      * media_files/README.md - Technical documentation
      * media_files/ADMIN_GUIDE.md - Django Admin user guide with examples
      * media_files/QUICKSTART.md - Quick start guide

2025-10-11 (Version 2.4)
========================

* **Performance Audit and Database Optimization**
  * Comprehensive N+1 query elimination across 13+ files
  * Admin pages optimized: 50-90% reduction in query count
  * Example: RentalRequestAdmin reduced from 301 queries to 3 queries (99% improvement)
  * API endpoints optimized: 30-70% faster loading times
 * Dashboard widgets optimized: 20-50% performance improvement
  
* **Admin Panel Query Optimization**
  * RentalRequestAdmin: Added select_related() for user, created_by, user__profile
  * RentalItemAdmin: Optimized FK queries for inventory_item, manufacturer, location
  * LicenseAdmin: Added prefetch_related() for tags, select_related() for profile/category
  * InventoryItemAdmin: Optimized all FK relationships (manufacturer, category, location, owner)
  * ProfileAdmin: Added select_related() for okuser and media_authority
  * ProjectAdmin: Optimized FK and M2M queries with prefetch_related()
  
* **API Endpoint Optimization**
  * api_get_all_rentals: Fixed paginator prefetch_related() loss issue
  * Implemented post-pagination re-optimization to preserve query efficiency
  * api_get_inventory_schedule: Added inventory_item to select_related()
  * api_users_detail: Added select_related() for okuser and media_authority
  * Reduced API response times by 30-70% under load
  
* **Widget and View Optimization**
  * EquipmentSet loops: Added prefetch_related() for items__inventory_item
  * Dashboard view: Added select_related() for profile.media_authority
  * Reduced widget rendering time by 20-50%
  
* **Documentation and Best Practices**
  * Added performance documentation for problematic methods (get_room_summary, get_inventory_number)
  * Created comprehensive PERFORMANCE_AUDIT_REPORT.md
  * Documented paginator prefetch_related() pitfalls
  * Added recommendations for caching and database indexes
  
* **Dashboard Chart Enhancements**
  * Added total count display in chart titles (e.g., "Age Structure (150)")
  * Added individual value labels in Y-axis for all bars
  * Enhanced data visibility in all dashboard graphs
  * Improved user experience with real-time sum calculations
  
* **Admin Filter UI Improvements**
  * Fixed text color and styling of "Reset" buttons in filters
  * Consistent button styling across datetime and numeric range filters
  * Improved button alignment and readability
  * Enhanced UX with proper CSS variable usage for theme compatibility

2025-10-10 (Version 2.3)
========================

* **API Enhancements**
  * Added token-based authentication API endpoint for license metadata
  * Implemented LicenseMetadataSerializer with comprehensive data export
  * Added `targetChannel` field for PeerTube integration (ActivityPub/Fediverse format)
  * Enhanced `originallyPublishedAt` logic with time extraction from planning system
  * Created comprehensive API tests with authorization and data validation

* **Admin Interface Improvements**
  * Enhanced Token Admin with staff-only user filtering and search functionality
  * Added Django AutocompleteSelect for improved user selection experience
 * Implemented API documentation modal with cURL, JavaScript, and Python examples
  * Added copy-to-clipboard functionality for API tokens and examples
  * Fixed Token registration conflicts and improved error handling
  * Enhanced UserAdmin with extended search fields (email, first_name, last_name)

* **Profile Model Updates**
  * Added `ausweisnummer` field for ID document number storage
  * Implemented data sharing permission checkboxes:
    * `phone_data_sharing_allowed` - permission to share phone number with third parties
    * `email_data_sharing_allowed` - permission to share email address with third parties
  * Organized admin fieldsets with collapsible sections for better UX
 * Excluded admin-only fields from user registration and profile edit forms
  * Enhanced ProfileResource for data export with new fields

* **Custom Widget Development**
  * Created TagsInputWidget for improved tags input in Django Admin
  * Replaced default JSONField with user-friendly interface
  * Added real-time tag preview and validation (maximum 4 tags)
  * Implemented interactive tag removal and automatic comma separation
 * Enhanced form validation with empty tag prevention and duplicate removal
 * Added support for null value handling and clean default display

* **Security and Privacy Enhancements**
  * Implemented GDPR-compliant data sharing permissions
  * Added admin-only access controls for sensitive profile fields
  * Enhanced token authentication with secure API endpoints
  * Improved user data protection with selective field exposure

* **Documentation and Testing**
  * Added comprehensive API documentation with usage examples
  * Created detailed admin interface documentation
  * Implemented extensive test coverage for new features
  * Added migration scripts for database schema updates
 * Enhanced inline code documentation and help texts

* **Database Migrations**
  * Added migration for new Profile model fields
  * Updated License model with tags field and default value changes
 * Implemented data migration for existing records
  * Added database indexes for improved search performance

* **Performance Optimizations**
  * Optimized database queries with select_related() and only() methods
  * Added composite indexes on Profile (first_name, last_name) for faster searches
  * Reduced database queries in API endpoints from 5+ to 1-2 per request
  * Implemented query optimization reducing data transfer by ~70%

* **Security Enhancements**
  * Added API rate limiting (10/hour for anonymous, 1000/hour for authenticated users)
  * Implemented comprehensive API access logging with user and IP tracking
  * Enhanced error handling with detailed logging for debugging
  * Added throttling protection against API abuse and DDoS attacks

* **Admin Interface Improvements**
  * Added fieldsets organization to LicenseAdmin (6 sections with collapsible panels)
  * Improved ProjectAdmin fieldsets with collapsible participant sections and descriptions
 * Added fieldsets to InventoryItemAdmin (5 sections grouped by functionality)
  * Enhanced ContributionAdmin with basic fieldsets for consistency
 * Improved UX with logical grouping: Basic Info → Details → Advanced (collapsed)
  * Reduced admin form scrolling by ~50-70% with smart field organization
  * Added helpful descriptions to complex sections (participant validation, auto-calculated fields)
  * Standardized readonly_fields across all admins for better data integrity

* **User Interface Enhancements**
  * Added Tags (Hashtags) field to user-facing License creation form
 * Integrated TagsInputWidget in License edit form for visual tag management
  * Added tag input with comma-separated values and visual badges
  * Implemented tag validation (max 4 tags) in user interface
 * User-friendly tag management with click-to-remove badges
  * Consistent tag experience between admin and user interfaces

* **Deployment Infrastructure Improvements**
  * Restructured deployment configuration with dedicated `deployment/` directory
  * Added comprehensive Docker deployment support with production-ready configuration
  * Added Gunicorn deployment guide with systemd service files
  * Created ready-to-use configurations for multiple German states (Bayern, NRW, OKMQ)
  * Enhanced configuration files with complete organization settings (description, opening_hours, broadcast times)

* **Documentation Enhancements**
  * Translated all deployment documentation to English
  * Added detailed deployment guides for Docker and Gunicorn methods
  * Created architecture diagrams and deployment comparison tables
  * Updated GitHub repository references throughout the codebase
  * Enhanced configuration file comments with complete state media institution list

* **Configuration Management**
  * Expanded organization configuration with new fields:
    * `description` - Organization description for welcome page
    * `opening_hours` - Formatted opening hours with line breaks
    * `broadcast_start` / `broadcast_end` - Broadcast slot configuration
  * Unified configuration structure across Docker and Gunicorn deployments
  * Added detailed inline documentation for all configuration options

* **Codebase Cleanup**
  * Removed deprecated example configurations from project root
  * Removed outdated systemd service files from scripts/ directory
  * Removed accidentally included odfpy man-pages (share/ directory)
  * Removed legacy development scripts (createsuperuser.py, test_data.py, etc.)
  * Consolidated all deployment-related files under `deployment/` directory
  * Unified requirements files: removed requirements-docker.txt, using single requirements.txt
  * Removed unused reportlab dependency

* **Security and Production Readiness**
  * Enhanced systemd service files with comprehensive security settings
  * Added production-specific environment variable handling
 * Improved SSL/HTTPS configuration examples
 * Added rate limiting and health check configurations for Nginx
  * Enhanced Docker security with user isolation and minimal privileges

2025-09-21
==========

* **Dashboard Analytics System** - Added comprehensive dashboard with interactive charts
  * Multiple chart types: doughnut, bar, horizontal bar with dynamic switching
  * Real-time data visualization for users, projects, licenses, and inventory
 * Export functionality for all chart data
  * Responsive design with adaptive height for large datasets

* **Admin Interface Enhancements**
  * Added direct dashboard link in Django admin menu
 * Hidden specific admin models (Alert Logs, Alert Thresholds, Funnel Metrics, User Journey Stages)
  * Improved admin navigation and user experience

* **Translation System Improvements**
  * Updated German and English translation files (.po/.mo)
  * Added chart-related translations (Doughnut Chart, Bar Chart, Horizontal Bar Chart)
  * Fixed translation compilation issues
  * Added dashboard-specific translation files

* **Chart System Features**
  * Extended color palette (15 colors) to prevent repetition
  * Adaptive container height based on data amount
  * Improved legend display with label truncation
  * Horizontal bar chart support with proper axis configuration
  * Enhanced tooltip functionality

* **Code Quality Improvements**
  * Updated .gitignore to exclude development files
  * Fixed JavaScript translation import issues
  * Improved error handling in dashboard widgets
  * Enhanced responsive design for mobile devices

2023-06-27
==========

* Change the "Nutzeranmeldung" pdf to a more recent version.

* Fix the gender count validation to include all genders which can be selected.
