========
ok_tools
========

A universal set of tools to support administrative tasks for community media organizations. Originally developed for the Offener Kanal system of Medienanstalt Sachsen-Anhalt, now configurable for any organization.

**Current Version**: 3
**Last Updated**: October 2025

Features
========

**Core Applications:**
- **User Registration** - User management with privacy controls and notification system
- **License Management** - Manage broadcasting licenses with tags and metadata export
- **Media Files Management** - Advanced video file management with metadata extraction, storage location tracking, and license synchronization
- **Planning Tools** - Calendar weeks and scheduling functionality with time extraction
- **Contributions Management** - Handle user contributions and submissions
- **Project Management** - Organize and track various projects
- **Inventory Management** - Track equipment and resources with serial numbers
- **Rental System** - Equipment rental management with expiration tracking
- **Dashboard Analytics** - Comprehensive data visualization and monitoring
- **Background Task Processing** - Asynchronous task execution with Celery for handling time-intensive operations
- **Monitoring & Metrics** - Prometheus integration for application performance monitoring and metrics collection

**Additional Features:**
- **Accessibility Compliance** - WCAG compliant interface
- **Multi-language Support** - German and English localization
- **Dashboard System** - Comprehensive activity monitoring with interactive charts
- **Admin Interface** - Django admin customization with direct dashboard access
- **REST API** - JSON endpoints for data access with token authentication
- **Token Authentication** - Secure API access with customizable permissions
- **PeerTube Integration** - ActivityPub/Fediverse format support for video publishing
- **Custom Widgets** - Enhanced form widgets for improved user experience
- **Data Privacy Controls** - GDPR-compliant data sharing permissions
- **Cron Jobs** - Automated rental expiration management
- **Interactive Charts** - Multiple chart types (doughnut, bar, horizontal bar) with data export
- **Real-time Analytics** - User journey tracking and funnel metrics
- **Alert System** - Automated monitoring and threshold-based notifications


Installation & Deployment
=========================

OK Tools supports two main deployment methods:

**Docker Deployment (Recommended for production):**
::

    git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git
    cd ok-tools
    chmod +x deployment/scripts/install.sh
    ./deployment/scripts/install.sh
**Note:** .cfg files are no longer used and have been replaced by .env files. Examples are located in the `deployment/configs` directory. The installation script will prompt for the necessary values.

See ``deployment/docker/README.md`` for detailed Docker setup instructions.

**Gunicorn Deployment (Traditional server setup):**
::

    git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git
    cd ok-tools
    python3.12 -m venv venv
    venv/bin/pip install -r requirements.txt
    venv/bin/pip install gunicorn

See ``deployment/gunicorn/README.md`` for detailed Gunicorn setup instructions.

**Development Setup:**
::

    git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git
    cd ok-tools
    python3.12 -m venv venv
    venv/bin/pip install -r requirements.txt

**Organization Configuration:**

The installation script will guide you through the configuration process. For manual configuration:

1. Copy the example environment file::

    cp deployment/configs/ok-bayern.env.template .env

2. Edit the environment file with your organization's details::

    # Organization Configuration
    ORG_NAME=Your Community Media Organization e.V.
    ORG_SHORT_NAME=Your CMO
    ORG_WEBSITE=https://your-organization.com
    ORG_EMAIL=info@your-organization.com
    ORG_ADDRESS=Your Address Here
    ORG_PHONE=+49 123 456789
    ORG_FAX=+49 123 456790
    ORG_DESCRIPTION=Welcome to our organization! We provide media services...
    ORG_OPENING_HOURS=Mon: 09:00 - 17:00\nTue-Fri: 09:00 - 18:00
    # State media institution (accessible to all users)
    STATE_MEDIA_INSTITUTION=MSA
    # Organization owner (accessible only to members)
    ORGANIZATION_OWNER=Your CMO
    # PeerTube integration (ActivityPub/Fediverse format)
    PEERTUBE_CHANNEL=@your-channel@peertube.your-domain.com

3. Run the setup command to create organizations in the database::

    python manage.py setup_organizations

   **Note:** Organizations are also created automatically on application startup,
   so this step is optional. Use it when you need to manually sync configuration changes.

**What Gets Created Automatically:**

When you configure ``state_media_institution`` and ``organization_owner``, the system automatically creates:

- **MediaAuthority** object (in ``/admin/registration/mediaauthority/``)
  - Your organization: "OK Bayern" (used for user profile association)
  
- **Organization** objects (in ``/admin/inventory/organization/``)
  - State institution: "BLM" (equipment accessible to all users)
  - Your organization: "OK Bayern" (equipment accessible only to members)

These objects are used for user profiles and equipment ownership/access control throughout the system.

**German State Media Institutions:**

The system supports all German state media institutions:

- **MSA** - Medienanstalt Sachsen-Anhalt
- **LFK** - Landesanstalt für Kommunikation Baden-Württemberg
- **BLM** - Bayerische Landeszentrale für neue Medien
- **mabb** - Medienanstalt Berlin-Brandenburg
- **brema** - Bremische Landesmedienanstalt
- **MA HSH** - Medienanstalt Hamburg / Schleswig-Holstein
- **MMV** - Medienanstalt Mecklenburg-Vorpommern
- **NLM** - Niedersächsische Landesmedienanstalt
- **LfM NRW** - Landesanstalt für Medien NRW
- **LMS** - Landesmedienanstalt Saarland
- **SLM** - Sächsische Landesmedienanstalt
- **TLM** - Thüringer Landesmedienanstalt

See the ``deployment/configs/`` directory for ready-to-use environment file templates for different German states.

3. Set the environment variable to point to your environment file::

    # For development (local)
    export OKTOOLS_ENV_FILE=/home/user/ok-tools/.env
    
    # For production server (typical paths)
    export OKTOOLS_ENV_FILE=/opt/ok-tools/.env
    # or
    export OKTOOLS_ENV_FILE=/etc/ok-tools/.env
    # or
    export OKTOOLS_ENV_FILE=/var/www/ok-tools/.env

4. Make the environment variable persistent::

    # Add to ~/.bashrc or ~/.profile for user-level
    echo 'export OKTOOLS_ENV_FILE=/opt/ok-tools/.env' >> ~/.bashrc
    
    # Or add to /etc/environment for system-wide
    echo 'OKTOOLS_ENV_FILE=/opt/ok-tools/.env' | sudo tee -a /etc/environment
    
    # For systemd services, add to service file:
    # Environment=OKTOOLS_ENV_FILE=/opt/ok-tools/.env

5. The system will use your organization's branding throughout the interface, forms, and communications.

**Dependencies:**
- Python 3.12+
- Django 5.2.5
- PostgreSQL (production) / SQLite (development)
- Redis (optional, for caching)

**Installation:**

All dependencies are managed in a single ``requirements.txt`` file::

    pip install -r requirements.txt

This file is used for:
- Local development
- Docker deployment
- Gunicorn/production deployment

Tests
=====

Install the testing dependencies::

   bin/pip install -r requirements.txt
   bin/pip install pytest pytest-cov pytest-django

Create static resources::

    OKTOOLS_ENV_FILE=.env bin/python manage.py collectstatic

Run the Tests using pytest::

    bin/pytest

**Test Coverage:**
- Unit tests for all applications
- Integration tests for API endpoints with token authentication
- API endpoint tests for license metadata export
- Admin interface tests for custom widgets and forms
- Coverage reporting with pytest-cov

Configuration
=============

We have provided environment file templates and comprehensive examples for production deployment.

**Configuration Files:**
- `.env` files - Environment configuration files (replacing .cfg files)
- `deployment/configs/*.env.template` - Environment file templates for different organizations
- `deployment/configs/*.cfg` - Legacy configuration files (no longer used)

**Environment Variables:**
- `OKTOOLS_ENV_FILE` - Path to environment file
- `DJANGO_SETTINGS_MODULE` - Django settings module
- `DATABASE_URL` - Database connection string

Maintenance/Initial Setup
=========================

Run the typical django scripts after install/update::

    OKTOOLS_ENV_FILE=.env bin/python manage.py migrate
    OKTOOLS_ENV_FILE=.env bin/python manage.py collectstatic
    OKTOOLS_ENV_FILE=.env bin/python manage.py compilemessages

You may want to create a superuser::

    OKTOOLS_ENV_FILE=.env bin/python manage.py createsuperuser

Run Server Locally
==================

To run the server locally you first need to specify an environment file. This
configuration is ment for testing only and should not be used in any way for
prouction due to security reasons.
::

    OKTOOLS_ENV_FILE=.env bin/python manage.py runserver

Production Deployment
=====================

OK Tools supports two production deployment methods:

**Docker Deployment (Recommended):**

See ``deployment/docker/README.md`` for comprehensive Docker setup instructions.

Quick start::

    pavlo@debian:~/docker$ cd ok_tools
    pavlo@debian:~/docker/ok_tools$ chmod +x deployment/scripts/install.sh
    pavlo@debian:~/docker/ok_tools$ ./deployment/scripts/install.sh
**Note:** .cfg files are no longer used and have been replaced by .env files. Examples are located in the `deployment/configs` directory. The installation script will prompt for the necessary values.

**Gunicorn Deployment (Traditional):**

See ``deployment/gunicorn/README.md`` for comprehensive Gunicorn setup instructions.

Quick start::

    sudo cp deployment/configs/ok-bayern.env.template /opt/ok-tools/.env
    # Edit environment file
    sudo cp deployment/gunicorn/*.service /etc/systemd/system/
    sudo cp deployment/gunicorn/*.timer /etc/systemd/system/
    sudo systemctl enable ok-tools ok-tools-cron.timer
    sudo systemctl start ok-tools

**Systemd Services (Gunicorn deployment):**
- `deployment/gunicorn/ok-tools.service` - Main application server
- `deployment/gunicorn/ok-tools-cron.service` - Rental expiration management
- `deployment/gunicorn/ok-tools-cron.timer` - Automated rental cleanup (every 30 min)

Import Legacy Data
==================

It is possible to import legacy data from Excel files (:code:`.xlsx`).

The import functionality requires:
- A workbook with worksheets named: :code:`users`, :code:`contributions`, :code:`categories`, :code:`repetitions`, :code:`projects`
- Configure the path in :code:`settings.py` via :code:`LEGACY_DATA` (default: :code:`../legacy_data/data.xlsx`)

**Note:** The legacy import script is a one-time migration tool. If you've already completed your data migration, this feature is not needed for daily operations.

Privacy Policy
==============

To include a privacy policy simply modify :code:`files/privacy_policy.html`.

Security
========

Without further actions the view to export the project dates
(:code:`admin/calendar_export`) is reachable without any authentication.

**Security Features:**
- CSRF protection enabled
- XSS protection headers
- SQL injection prevention
- User authentication and authorization
- Role-based access control
- Token-based API authentication with rate limiting
- API throttling (100/hour anonymous, 1000/hour authenticated)
- Comprehensive API access logging with audit trail
- GDPR-compliant data sharing permissions
- Admin-only access controls for sensitive fields
- Enhanced privacy controls for user data

Backup
======

To create backups you can simply copy the .sqlite file::

    cp db.sqlite3 backup.sqlite3

**Automated Backups:**
- Database backup scripts available
- Cron job configuration for regular backups
- Backup rotation and cleanup

Working with translations
=========================

Find new messages like this::

    OKTOOLS_ENV_FILE=.env bin/python manage.py makemessages -l de --ignore lib

**Translation Management:**
::

    # Create/update translation files
    bin/python manage.py makemessages -l de -l en

    # Compile translations
    bin/python manage.py compilemessages

    # Collect static files
    bin/python manage.py collectstatic

**Supported Languages:**
- German (de) - Primary language
- English (en) - Secondary language

**Translation Files:**
- `ok_tools/locale/de/LC_MESSAGES/django.po` - German translations
- `ok_tools/locale/en/LC_MESSAGES/django.po` - English translations
- `ok_tools/locale/*/LC_MESSAGES/djangojs.po` - JavaScript translations

Development
===========

**Code Quality:**
- Pre-commit hooks configuration
- isort configuration for import sorting
- Black code formatting
- Flake8 linting

**Testing:**
- pytest configuration
- Coverage reporting
- Test data fixtures

**Performance:**
- **Database Query Optimization:**
  - Comprehensive N+1 query elimination across all admin panels
  - Smart use of select_related() and prefetch_related() for FK and M2M relations
  - Optimized API endpoints with 30-70% faster loading times
  - Admin pages reduced queries by 50-90% (e.g., 301 queries → 3 queries)
  - Dashboard widgets optimized with prefetch strategies
- **Indexing Strategy:**
  - Composite indexes on Profile (first_name, last_name)
  - Strategic indexes for filtered fields (status, dates, flags)
- **API Performance:**
  - Rate limiting and throttling (100/hour anonymous, 1000/hour authenticated)
  - Comprehensive logging and monitoring
  - Query optimization reducing data transfer by ~70%
- **Paginator Optimization:**
  - Special handling to preserve prefetch_related() after pagination
  - Prevents query multiplication on paginated endpoints

**Static Files:**
- CSS and JavaScript compilation
- Asset optimization
- Responsive design support

**API Documentation:**
- REST API endpoints with token authentication
- JSON response formats with comprehensive metadata
- Authentication requirements and security
- PeerTube integration with ActivityPub/Fediverse format
- License metadata export with planning system integration
- Custom widget development and integration
- Admin interface enhancements and customization

**Admin Interface Enhancements:**
- Custom Token Admin with staff-only filtering
- Enhanced user search with autocomplete functionality
- API documentation modal with code examples
- Copy-to-clipboard functionality for tokens
- Improved form widgets for better user experience

**Privacy and Security:**
- GDPR-compliant data sharing permissions
- Admin-only access controls for sensitive fields
- Enhanced token authentication system
- Selective field exposure in user forms

Deployment Architecture
=======================

**Infrastructure Options:**

1. **Docker Deployment** - Containerized setup with Nginx, Gunicorn, PostgreSQL, Redis
   - Automated SSL certificate management
   - Isolated environment with security hardening
   - One-command deployment and updates
   - See ``deployment/docker/README.md``

2. **Gunicorn Deployment** - Traditional server setup with systemd
   - Full system control and optimization
   - Integration with existing infrastructure
   - Detailed security settings
   - See ``deployment/gunicorn/README.md``

**Deployment Resources:**
- Ready-to-use environment file templates in ``deployment/configs/``
- Comprehensive deployment guides in ``deployment/README.md``
- Production-ready systemd service files
- Nginx configuration with rate limiting and security headers

**Monitoring:**
- Application logs via journalctl (systemd) or docker logs
- Error tracking and debugging
- Performance monitoring
- Health check endpoints

Support
========

For support and questions:
- GitHub Issues: https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools/issues
- Documentation: See inline code comments and docstrings
- Testing: Run test suite for verification
- API Documentation: See README_TOKEN_ADMIN.md for API usage examples
- Admin Interface: See README_PROFILE_UPDATES.md for admin features
- Custom Widgets: See README_TAGS_WIDGET.md for widget development

**Contributing:**
- Fork the repository
- Create feature branch
- Submit pull request
- Follow coding standards
