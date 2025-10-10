# Gunicorn Deployment for OK Tools

## Quick Start

1. **Prepare the server:**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3.12 python3.12-venv python3-pip postgresql nginx git
   
   # CentOS/RHEL
   sudo dnf install python3.12 python3-pip postgresql-server nginx git
   ```

2. **Create user and directories:**
   ```bash
   sudo useradd -m -s /bin/bash oktools
   sudo mkdir -p /opt/ok-tools/{config,logs,static,media}
   sudo chown -R oktools:oktools /opt/ok-tools
   ```

3. **Clone and configure the application:**
   ```bash
   sudo -u oktools git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git /opt/ok-tools/app
   cd /opt/ok-tools/app
   sudo -u oktools python3.12 -m venv /opt/ok-tools/venv
   sudo -u oktools /opt/ok-tools/venv/bin/pip install -r requirements.txt
   sudo -u oktools /opt/ok-tools/venv/bin/pip install gunicorn
   ```

4. **Copy and configure the settings:**
   ```bash
   sudo -u oktools cp deployment/gunicorn/production.cfg.example /opt/ok-tools/config/production.cfg
   sudo -u oktools nano /opt/ok-tools/config/production.cfg
   ```

5. **Configure the database:**
   ```bash
   sudo -u postgres createuser oktools
   sudo -u postgres createdb oktools -O oktools
   sudo -u postgres psql -c "ALTER USER oktools PASSWORD 'your-strong-password';"
   ```

6. **Run migrations:**
   ```bash
   sudo -u oktools bash -c "
   export OKTOOLS_CONFIG_FILE=/opt/ok-tools/config/production.cfg
   cd /opt/ok-tools/app
   /opt/ok-tools/venv/bin/python manage.py migrate
   /opt/ok-tools/venv/bin/python manage.py collectstatic --noinput
   /opt/ok-tools/venv/bin/python manage.py setup_organizations
   /opt/ok-tools/venv/bin/python manage.py createsuperuser
   "
   ```

   **Note:** The `setup_organizations` command will create `MediaAuthority` and `Organization` 
   objects based on your configuration. They are also created automatically when the application starts.

7. **Install systemd services:**
   ```bash
   sudo cp deployment/gunicorn/ok-tools.service /etc/systemd/system/
   sudo cp deployment/gunicorn/ok-tools-cron.service /etc/systemd/system/
   sudo cp deployment/gunicorn/ok-tools-cron.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable ok-tools ok-tools-cron.timer
   sudo systemctl start ok-tools ok-tools-cron.timer
   ```

8. **Configure Nginx:**
   ```bash
   sudo cp deployment/gunicorn/nginx-ok-tools.conf /etc/nginx/sites-available/ok-tools
   sudo ln -s /etc/nginx/sites-available/ok-tools /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## File Structure

```
deployment/gunicorn/
├── README.md                      # This file
├── production.cfg.example        # Production configuration example
├── gunicorn.conf.py              # Gunicorn configuration
├── ok-tools.service              # Systemd service for application
├── ok-tools-cron.service         # Systemd service for cron tasks
├── ok-tools-cron.timer           # Systemd timer for cron
└── nginx-ok-tools.conf           # Nginx configuration
```

## Management

```bash
# Service status
sudo systemctl status ok-tools
sudo systemctl status ok-tools-cron.timer

# Restart after code update
cd /opt/ok-tools/app
sudo -u oktools git pull
sudo -u oktools /opt/ok-tools/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart ok-tools

# View logs
sudo journalctl -u ok-tools -f
sudo tail -f /opt/ok-tools/logs/gunicorn.log

# Database backup
sudo -u postgres pg_dump oktools > backup-$(date +%Y%m%d).sql
```

## SSL/HTTPS

Use certbot to obtain Let's Encrypt certificates:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```
