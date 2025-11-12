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

OK Tools uses Docker for production deployment. The installation process consists of 5 steps:

**Step 1: Clone the Repository**
::

    git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git
    cd ok-tools

**Step 2: Create Your Configuration**

Copy one of the configuration templates from ``deployment/configs/`` and customize it:
::

    cp deployment/configs/okmq.env.template deployment/configs/my-org.env.template
    # Edit deployment/configs/my-org.env.template and replace __REPLACE_ME__ placeholders

Available templates:
- ``okmq.env.template`` - OKMQ configuration template
- ``ok-bayern.env.template`` - Bayern configuration template
- ``ok-nrw.env.template`` - NRW configuration template

**Step 3: Add Logo and Favicon**

Place your organization's branding files in ``deployment/img/``:
::

    cp /path/to/your/logo.png deployment/img/logo.png
    cp /path/to/your/favicon.ico deployment/img/favicon.ico

**Step 4: Run Installation Script**
::

    chmod +x deployment/scripts/install.sh
    ./deployment/scripts/install.sh

The script will guide you through installation type selection (Production, Local Network, or Localhost) and create a production directory at ``../ok_tools_production``.

**Step 5: Update the Application**

After installation, updates are performed from the production directory:
::

    cd ../ok_tools_production
    ./update.sh

The update script automatically pulls the latest code from git, updates Docker containers, runs migrations, and restarts services.

See ``deployment/README.md`` for detailed installation instructions.

**Organization Configuration:**

The installation script will guide you through the configuration process. Configuration templates are located in ``deployment/configs/`` directory.

Key organization settings in the configuration file:
::

    # Organization Configuration
    ORG_NAME=Your Community Media Organization e.V.
    ORG_SHORT_NAME=Your CMO
    ORG_WEBSITE=https://your-organization.com
    ORG_EMAIL=info@your-organization.com
    ORG_ADDRESS=Your Address Here\nCity, Postal Code
    ORG_PHONE=+49 123 456789
    ORG_FAX=+49 123 456790
    ORG_DESCRIPTION=Welcome to our organization! We provide media services...
    ORG_OPENING_HOURS=Mon: 09:00 - 17:00\nTue-Fri: 09:00 - 18:00
    STATE_MEDIA_INSTITUTION=MSA
    ORG_ORGANIZATION_OWNER=Your CMO

**Note:** Use ``\n`` for line breaks in ``ORG_ADDRESS`` and ``ORG_OPENING_HOURS``. Organizations are created automatically on application startup.

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

**Note:** For Docker deployment, the `.env` file is automatically created in the production directory (``../ok_tools_production/.env``) during installation. The system will use your organization's branding throughout the interface, forms, and communications.

**Dependencies:**
- Docker and Docker Compose
- PostgreSQL (via Docker)
- Redis (via Docker, for caching and Celery)

All dependencies are automatically installed in Docker containers during deployment. The application uses Python 3.12+ and Django 5.2.5 inside the container.

Tests
=====

Tests can be run inside Docker containers::

    cd ../ok_tools_production
    docker compose exec web python manage.py test

Or using pytest::

    docker compose exec web pytest

**Test Coverage:**
- Unit tests for all applications
- Integration tests for API endpoints with token authentication
- API endpoint tests for license metadata export
- Admin interface tests for custom widgets and forms
- Coverage reporting with pytest-cov

Configuration
=============

Configuration is done via environment variables in `.env` file located in the production directory (``../ok_tools_production/.env``).

**Configuration Files:**
- `.env` file - Environment configuration file (created during installation)
- `deployment/configs/*.env.template` - Environment file templates for different organizations

**Key Configuration Variables:**
- `DJANGO_SECRET_KEY` - Secret key for Django (required)
- `POSTGRES_PASSWORD` - Database password (required)
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `ORG_NAME`, `ORG_SHORT_NAME` - Organization information
- `ORG_ADDRESS`, `ORG_OPENING_HOURS` - Contact information (use `\n` for line breaks)

See ``deployment/docs/ENV_VARIABLES.md`` for complete reference.

Maintenance
===========

All maintenance tasks are performed inside Docker containers.

**After installation or update:**

The installation and update scripts automatically run::
- Database migrations
- Static files collection
- Translation compilation

**Manual maintenance commands:**

Run migrations::

    cd ../ok_tools_production
    docker compose exec web python manage.py migrate

Collect static files::

    docker compose exec web python manage.py collectstatic --noinput

Compile translations::

    docker compose exec web python manage.py compilemessages

Create superuser::

    docker compose exec web python manage.py createsuperuser

Production Deployment
=====================

OK Tools uses Docker for production deployment.

**Docker Deployment:**

See ``deployment/README.md`` for comprehensive Docker setup instructions.

Quick start::

    git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git
    cd ok-tools
    # Copy and customize config template
    cp deployment/configs/okmq.env.template deployment/configs/my-org.env.template
    # Add logo and favicon to deployment/img/
    # Run installation
    chmod +x deployment/scripts/install.sh
    ./deployment/scripts/install.sh
    # For updates
    cd ../ok_tools_production
    ./update.sh

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

**Automated Backups:**

Database backups are automatically created by the periodic task ``run_backup_db`` (runs daily at 3:00 AM by default). Backups are stored in ``../ok_tools_production/backups/`` directory.

**Manual backup:**

Create a database backup manually::

    cd ../ok_tools_production
    docker compose exec -T db pg_dump -U oktools oktools > backups/manual-backup-$(date +%Y%m%d-%H%M%S).sql

**Backup management:**
- Automatic backup rotation (keeps last 5 backups)
- Backup cleanup task runs daily
- Backups include database dump and configuration files

Working with translations
=========================

**Create/update translation files:**

Translation files are edited in the project directory, then compiled in Docker::

    # In project directory - create/update translation files
    docker compose -f docker-local/docker-compose.yml exec web python manage.py makemessages -l de -l en

    # In production directory - compile translations
    cd ../ok_tools_production
    docker compose exec web python manage.py compilemessages

**Supported Languages:**
- German (de) - Primary language
- English (en) - Secondary language

**Translation Files:**
- `ok_tools/locale/de/LC_MESSAGES/django.po` - German translations
- `ok_tools/locale/en/LC_MESSAGES/django.po` - English translations
- `ok_tools/locale/*/LC_MESSAGES/djangojs.po` - JavaScript translations

**Note:** Translation compilation is automatically performed during installation and updates.

Technical Details
==================

**Code Quality:**
- Pre-commit hooks configuration
- isort configuration for import sorting
- Black code formatting
- Flake8 linting

**Testing:**
- pytest configuration
- Coverage reporting
- Test data fixtures
- Tests run inside Docker containers

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

**Infrastructure:**

**Docker Deployment** - Containerized setup with Nginx, PostgreSQL, Redis
- Automated SSL certificate management
- Isolated environment with security hardening
- One-command deployment and updates
- See ``deployment/README.md``

**Deployment Resources:**
- Ready-to-use environment file templates in ``deployment/configs/``
- Comprehensive deployment guides in ``deployment/README.md``
- Nginx configuration with rate limiting and security headers

**Monitoring:**
- Application logs via docker logs
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
