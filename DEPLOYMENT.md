# Wine Cellar - Deployment Guide

This guide covers launching the Wine Cellar application from source.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Development Setup](#development-setup)
3. [Production Setup](#production-setup)
4. [Configuration Reference](#configuration-reference)
5. [Security Checklist](#security-checklist)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Development
```bash
./run_local.sh
# Access at: http://localhost:8000
```

### Production
```bash
sudo ./run_prod_local.sh start
# Access at: http://your-server-ip
```

---

## Development Setup

**Prerequisites:**
- Python 3.11+
- Node.js 20+ (for building frontend assets)

**Setup:**
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
npm install
npm run build

# 3. Create environment file
cp .env.dev-sample .env.dev
# Edit .env.dev with your settings

# 4. Run migrations and start server
./run_local.sh
```

**Access:**
- Main site: http://localhost:8000
- Admin: http://localhost:8000/admin/
- Default credentials: admin / change_me

---

## Production Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Domain name (optional, for HTTPS)

### Step 1: Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install production dependencies
pip install -r requirements/prod.txt
pip install gunicorn

# Build frontend
npm install
npm run build:prod
```

### Step 2: Configure Environment

Create `.env.prod.local`:
```bash
DJANGO_DEBUG=False
SECRET_KEY=<your-secure-64-char-key>
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,your-domain.com,your-ip"
DJANGO_CSRF_TRUSTED_ORIGINS="http://your-domain.com,http://your-ip"
SITE_URL=http://your-domain.com
SQL_ENGINE=django.db.backends.sqlite3
SQL_DATABASE=db.sqlite3
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
ADMIN_USER=admin
ADMIN_USER_EMAIL=your-email@example.com
ADMIN_USER_PASSWORD=<strong-password>
```

### Step 3: Generate a Secure Secret Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output to `SECRET_KEY` in `.env.prod.local`.

### Step 4: Start Production Server

```bash
# Start server (requires sudo for port 80)
sudo ./run_prod_local.sh start

# Check status
./run_prod_local.sh status

# View logs
./run_prod_local.sh logs

# Stop server
sudo ./run_prod_local.sh stop
```

**Access:**
- Main site: http://your-server-ip (port 80)
- Admin: http://your-server-ip/admin/

---

## Alternative: Run on Port 8000 (No Sudo)

Edit `run_prod_local.sh` and change `--bind 0.0.0.0:80` to `--bind 0.0.0.0:8000`:
```bash
./run_prod_local.sh start
# Access at http://your-ip:8000
```

---

## Systemd Service (Auto-Start on Boot)

Create `/etc/systemd/system/wine-cellar.service`:

```ini
[Unit]
Description=Wine Cellar Gunicorn Server
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/path/to/wine
Environment="PATH=/path/to/wine/venv/bin"
EnvironmentFile=/path/to/wine/.env.prod.local
ExecStart=/path/to/wine/venv/bin/gunicorn wine_cellar.conf.wsgi:application --bind 0.0.0.0:80 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Then enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable wine-cellar
sudo systemctl start wine-cellar
```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | Django secret key (64+ chars) |
| `DJANGO_DEBUG` | No | False | Enable debug mode (never in prod!) |
| `DJANGO_ALLOWED_HOSTS` | Yes | - | Comma-separated list of allowed hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes | - | Comma-separated list of trusted origins |
| `SITE_URL` | Yes | - | Full URL of your site |
| `SQL_ENGINE` | No | sqlite3 | Database engine |
| `SQL_DATABASE` | No | db.sqlite3 | Database path/name |
| `ADMIN_USER` | No | admin | Initial admin username |
| `ADMIN_USER_EMAIL` | No | - | Admin email address |
| `ADMIN_USER_PASSWORD` | Yes | - | Admin password |
| `DJANGO_ENABLE_SIGNUPS` | No | False | Allow new user registrations |

---

## Security Checklist

### Before Going Live

- [ ] Generate a new `SECRET_KEY` (minimum 64 characters)
- [ ] Set `DJANGO_DEBUG=False`
- [ ] Use strong password for `ADMIN_USER_PASSWORD`
- [ ] Configure `DJANGO_ALLOWED_HOSTS` with only your domain/IP
- [ ] Configure `DJANGO_CSRF_TRUSTED_ORIGINS` correctly
- [ ] Set up HTTPS (using nginx/caddy as reverse proxy)
- [ ] Configure firewall to allow only necessary ports
- [ ] Review and restrict `DJANGO_ENABLE_SIGNUPS`
- [ ] Set up regular database backups

---

## Troubleshooting

### Common Issues

**1. "Connection Refused" Error**
- Check firewall rules allow traffic on the port
- Verify server is running: `./run_prod_local.sh status`
- Check logs: `./run_prod_local.sh logs`

**2. "DisallowedHost" Error**
- Add your domain/IP to `DJANGO_ALLOWED_HOSTS` in `.env.prod.local`
- Restart server: `sudo ./run_prod_local.sh restart`

**3. "CSRF Verification Failed"**
- Add your URL to `DJANGO_CSRF_TRUSTED_ORIGINS`
- Include the protocol (http:// or https://)

**4. Static Files Not Loading**
- Run: `python manage.py collectstatic --no-input`
- Ensure WhiteNoise is configured in settings

### Useful Commands

```bash
# Enter Django shell
source venv/bin/activate
python manage.py shell

# Create new superuser
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input
```

---

## Notes

1. **Port 80 requires sudo** - Running on port 80 requires root privileges
2. **SQLite for simplicity** - Uses SQLite database (fine for personal use)
3. **Static files** - Served by WhiteNoise middleware
4. **Background tasks** - Celery not configured for source-only setup
