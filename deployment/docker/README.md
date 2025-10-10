# Docker Deployment for OK Tools

## Quick Start

1. **Copy the example configuration:**
   ```bash
   cp deployment/docker/docker-production.cfg.example docker-production.cfg
   ```

2. **Edit the configuration for your organization:**
   ```bash
   nano docker-production.cfg
   ```

3. **Start the containers:**
   ```bash
   docker-compose -f deployment/docker/docker-compose.production.yml up -d
   ```

4. **Perform initial setup:**
   ```bash
   # Database migrations
   docker-compose -f deployment/docker/docker-compose.production.yml exec web python manage.py migrate
   
   # Create superuser
   docker-compose -f deployment/docker/docker-compose.production.yml exec web python manage.py createsuperuser
   
   # Collect static files
   docker-compose -f deployment/docker/docker-compose.production.yml exec web python manage.py collectstatic --noinput
   ```

## File Structure

```
deployment/docker/
├── README.md                           # This file
├── docker-compose.production.yml       # Production Docker Compose
├── docker-compose.development.yml      # Development Docker Compose  
├── Dockerfile.production              # Production Dockerfile
├── nginx.conf                         # Nginx configuration
├── docker-production.cfg.example     # Production configuration example
└── docker-development.cfg.example    # Development configuration example
```

## Organization Configuration

Edit `docker-production.cfg` for your organization:

```ini
[organization]
name = Your Organization e.V.
short_name = YO
website = https://your-domain.com
email = info@your-domain.com
address = Your Address\nCity, Postal Code
phone = +49 123 456789
state_media_institution = MSA  # Or LFK, BLM, etc.
organization_owner = YO
```

**Important:** After the first startup, organizations (`MediaAuthority` and `Organization`) will be created **automatically** based on the configuration. You don't need to create them manually through the admin panel.

For manual organization synchronization after configuration changes:
```bash
docker-compose -f deployment/docker/docker-compose.production.yml exec web python manage.py setup_organizations
```

## Management

```bash
# View logs
docker-compose -f deployment/docker/docker-compose.production.yml logs -f web

# Stop
docker-compose -f deployment/docker/docker-compose.production.yml down

# Update code
git pull
docker-compose -f deployment/docker/docker-compose.production.yml build web
docker-compose -f deployment/docker/docker-compose.production.yml up -d

# Database backup
docker-compose -f deployment/docker/docker-compose.production.yml exec db pg_dump -U oktools oktools > backup.sql
```

## SSL/HTTPS

For production with SSL, use nginx-proxy or Traefik, or configure SSL in nginx.conf.
