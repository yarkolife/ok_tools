========
ok_tools
========

A universal set of tools to support administrative tasks for community media organizations. Originally developed for the Offener Kanal system of Medienanstalt Sachsen-Anhalt, now configurable for any organization.

**Current Version**: 2.2
**Last Updated**: October 2025

Features
========

**Core Applications:**
- **Contributions Management** - Handle user contributions and submissions
- **Inventory Management** - Track equipment and resources with serial numbers
- **License Management** - Manage broadcasting licenses and youth protection categories
- **Rental System** - Equipment rental management with expiration tracking
- **Planning Tools** - Calendar weeks and scheduling functionality
- **Project Management** - Organize and track various projects
- **User Registration** - User management with notification system
- **Dashboard Analytics** - Comprehensive data visualization and monitoring

**Additional Features:**
- **Accessibility Compliance** - WCAG compliant interface
- **Multi-language Support** - German and English localization
- **Dashboard System** - Comprehensive activity monitoring with interactive charts
- **Admin Interface** - Django admin customization with direct dashboard access
- **REST API** - JSON endpoints for data access
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
    cp deployment/docker/docker-production.cfg.example docker-production.cfg
    # Edit docker-production.cfg for your organization
    docker-compose -f deployment/docker/docker-compose.production.yml up -d

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

1. Copy the example configuration file::

    cp organization.cfg.example your-organization.cfg

2. Edit the configuration file with your organization's details::

    [organization]
    name = Your Community Media Organization e.V.
    short_name = Your CMO
    website = https://your-organization.com
    email = info@your-organization.com
    address = Your Address Here
    phone = +49 123 456789
    fax = +49 123 456790
    description = Welcome to our organization! We provide media services...
    opening_hours = Mon: 09:00 - 17:00\n    Tue-Fri: 09:00 - 18:00
    # State media institution (accessible to all users)
    state_media_institution = MSA
    # Organization owner (accessible only to members)
    organization_owner = Your CMO

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

See the ``deployment/configs/`` directory for ready-to-use configurations for different German states.

3. Set the environment variable to point to your config file::

    # For development (local)
    export OKTOOLS_CONFIG_FILE=/home/user/ok-tools/your-organization.cfg
    
    # For production server (typical paths)
    export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg
    # or
    export OKTOOLS_CONFIG_FILE=/etc/ok-tools/organization.cfg
    # or
    export OKTOOLS_CONFIG_FILE=/var/www/ok-tools/config/organization.cfg

4. Make the environment variable persistent::

    # Add to ~/.bashrc or ~/.profile for user-level
    echo 'export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg' >> ~/.bashrc
    
    # Or add to /etc/environment for system-wide
    echo 'OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg' | sudo tee -a /etc/environment
    
    # For systemd services, add to service file:
    # Environment=OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg

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

    OKTOOLS_CONFIG_FILE=test.cfg bin/python manage.py collectstatic

Run the Tests using pytest::

    bin/pytest

**Test Coverage:**
- Unit tests for all applications
- Integration tests for API endpoints
- Coverage reporting with pytest-cov

Configuration
=============

We have provided a minimal config (test.cfg) and comprehensive examples for production deployment.

**Configuration Files:**
- `test.cfg` - Development and testing configuration
- `organization.cfg.example` - General organization configuration template
- `deployment/docker/docker-production.cfg.example` - Docker production configuration
- `deployment/gunicorn/production.cfg.example` - Gunicorn production configuration
- `deployment/configs/*.cfg` - Ready-to-use configurations for specific organizations

**Environment Variables:**
- `OKTOOLS_CONFIG_FILE` - Path to configuration file
- `DJANGO_SETTINGS_MODULE` - Django settings module
- `DATABASE_URL` - Database connection string

Maintenance/Initial Setup
=========================

Run the typical django scripts after install/update::

    OKTOOLS_CONFIG_FILE=yourconfig.cfg bin/python manage.py migrate
    OKTOOLS_CONFIG_FILE=yourconfig.cfg bin/python manage.py collectstatic
    OKTOOLS_CONFIG_FILE=yourconfig.cfg bin/python manage.py compilemessages

You may want to create a superuser::

    OKTOOLS_CONFIG_FILE=yourconfig.cfg bin/python manage.py createsuperuser

Run Server Locally
==================

To run the server locally you first need to specify a config file. This
configuration is ment for testing only and should not be used in any way for
prouction due to security reasons.
::

    OKTOOLS_CONFIG_FILE=test.cfg bin/python manage.py runserver

Production Deployment
=====================

OK Tools supports two production deployment methods:

**Docker Deployment (Recommended):**

See ``deployment/docker/README.md`` for comprehensive Docker setup instructions.

Quick start::

    cp deployment/docker/docker-production.cfg.example docker-production.cfg
    # Edit docker-production.cfg for your organization
    docker-compose -f deployment/docker/docker-compose.production.yml up -d

**Gunicorn Deployment (Traditional):**

See ``deployment/gunicorn/README.md`` for comprehensive Gunicorn setup instructions.

Quick start::

    sudo cp deployment/gunicorn/production.cfg.example /opt/ok-tools/config/production.cfg
    # Edit configuration
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

    OKTOOLS_CONFIG_FILE=test.cfg bin/python manage.py makemessages -l de --ignore lib

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

**Static Files:**
- CSS and JavaScript compilation
- Asset optimization
- Responsive design support

**API Documentation:**
- REST API endpoints
- JSON response formats
- Authentication requirements

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
- Ready-to-use configurations in ``deployment/configs/``
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

**Contributing:**
- Fork the repository
- Create feature branch
- Submit pull request
- Follow coding standards
