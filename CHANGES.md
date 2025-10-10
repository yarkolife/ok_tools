CHANGELOG
=========

2025-10-10
==========

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
