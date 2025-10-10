# OK Tools Deployment Guide

OK Tools supports two main production deployment methods:

## 🐳 Docker Deployment (Recommended)

**Advantages:**
- Easy installation and updates
- Isolated environment
- Includes PostgreSQL, Redis, Nginx
- Automatic SSL certificates
- Pre-configured security settings

**Best for:**
- Quick deployment
- Teams without deep system administration knowledge
- Modern cloud platforms

📖 **[Detailed guide: deployment/docker/README.md](docker/README.md)**

### Quick start:
```bash
cp deployment/docker/docker-production.cfg.example docker-production.cfg
# Edit docker-production.cfg for your organization
docker-compose -f deployment/docker/docker-compose.production.yml up -d
```

## 🚀 Gunicorn Deployment (Traditional)

**Advantages:**
- Full system control
- Performance optimization
- Integration with existing infrastructure
- Configuration flexibility

**Best for:**
- Experienced system administrators
- Integration with existing servers
- Specific security requirements

📖 **[Detailed guide: deployment/gunicorn/README.md](gunicorn/README.md)**

### Quick start:
```bash
# Create user and directories
sudo useradd -m oktools
sudo mkdir -p /opt/ok-tools/{config,logs,static,media}

# Install application
git clone https://github.com/Offener-Kanal-Merseburg-Querfurt/ok-tools.git /opt/ok-tools/app
cd /opt/ok-tools/app
python3.12 -m venv /opt/ok-tools/venv
/opt/ok-tools/venv/bin/pip install -r requirements.txt gunicorn

# Configuration
cp deployment/gunicorn/production.cfg.example /opt/ok-tools/config/production.cfg
# Edit configuration

# Install systemd services
sudo cp deployment/gunicorn/*.service /etc/systemd/system/
sudo cp deployment/gunicorn/*.timer /etc/systemd/system/
sudo systemctl enable ok-tools ok-tools-cron.timer
```

## 📁 Ready-made Configurations

The `deployment/configs/` folder contains ready-made configurations for various organizations:

- `okmq-production.cfg` - Original OKMQ (Sachsen-Anhalt, MSA)
- `ok-bayern-production.cfg` - For Bayern (BLM)
- `ok-nrw-production.cfg` - For NRW (LfM NRW)

## 🔐 Security

Both deployment methods include:

- **HTTPS/SSL** - Required for production
- **Rate limiting** - Attack protection
- **Security headers** - XSS, CSRF protection
- **Process isolation** - Minimal privileges
- **Logging** - Security monitoring

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │   OK Tools      │    │  PostgreSQL     │
│  (Load Balancer │───▶│   (Django +     │───▶│   (Database)    │
│   + SSL Term.)  │    │    Gunicorn)    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────▶│     Redis       │              │
                        │    (Cache)      │              │
                        └─────────────────┘              │
                                 │                       │
                        ┌─────────────────┐              │
                        │   Cron Jobs     │              │
                        │ (Expire Rentals)│──────────────┘
                        └─────────────────┘
```

## 📊 Comparison

| Criteria | Docker | Gunicorn |
|----------|---------|----------|
| Installation ease | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Performance | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Configuration flexibility | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Isolation | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Updates | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Monitoring | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 🆘 Support

If you encounter problems:

1. Check logs: `docker logs` or `journalctl -u ok-tools`
2. Verify configuration correctness
3. Check database connection
4. Create an issue in the repository with a detailed description
