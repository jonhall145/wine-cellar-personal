# Deployment Guide

This guide covers all deployment options for Wine Cellar, from local development to production.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Production Deployment](#production-deployment)
3. [HTTPS Configuration](#https-configuration)
4. [Email Configuration](#email-configuration)
5. [Systemd Service](#systemd-service-auto-start)
6. [Troubleshooting](#troubleshooting)

---

## Development Setup

### Quick Start

```bash
# Clone and install
git clone https://github.com/jonhall145/wine-cellar-personal.git
cd wine-cellar-personal
make install

# Start server
make server
# Visit http://localhost:8003
```

### Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
npm install
npm run build

# Set up environment
cp .env.dev-sample .env.dev

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start server
./run_local.sh
```

**Access:**
- Main site: http://localhost:8000
- Admin: http://localhost:8000/admin/

### Development Commands

| Command | Description |
|---------|-------------|
| `make install` | Install dependencies and set up database |
| `make server` | Start dev server on port 8003 |
| `make watch` | Dev server with frontend hot reload |
| `make pytest` | Run backend tests |
| `make lint` | Run all linters |
| `make fixtures` | Load sample data |

---

## Production Deployment

### Prerequisites

- Python 3.12+
- Node.js 20+
- Domain name (optional, for HTTPS)
- PostgreSQL (recommended) or SQLite

### Installation Steps

#### 1. Install Dependencies

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

#### 2. Configure Environment

Create `.env.prod.local`:

```bash
# Core Settings
DJANGO_DEBUG=False
SECRET_KEY=<your-secure-64-char-key>
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,your-domain.com,your-ip"
DJANGO_CSRF_TRUSTED_ORIGINS="http://your-domain.com,http://your-ip"
SITE_URL=http://your-domain.com

# Database (SQLite for simple setup)
SQL_ENGINE=django.db.backends.sqlite3
SQL_DATABASE=db.sqlite3

# Or PostgreSQL for production
# DATABASE_URL=postgres://user:password@localhost:5432/winecellar

# Admin User
ADMIN_USER=admin
ADMIN_USER_EMAIL=your-email@example.com
ADMIN_USER_PASSWORD=<strong-password>

# Django Settings Module
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
```

#### 3. Generate Secret Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output to `SECRET_KEY` in `.env.prod.local`.

#### 4. Prepare Static Files

```bash
source venv/bin/activate
python manage.py collectstatic --no-input
```

#### 5. Start Production Server

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

#### Alternative: Run on Port 8000 (No Sudo)

Edit `run_prod_local.sh` and change `--bind 0.0.0.0:80` to `--bind 0.0.0.0:8000`:

```bash
./run_prod_local.sh start
# Access at http://your-ip:8000
```

---

## HTTPS Configuration

Mobile browsers require HTTPS to access the camera for barcode scanning. Choose one of these options:

### Option 1: Caddy with Domain Name (Recommended)

Caddy automatically obtains and renews Let's Encrypt certificates.

#### Install Caddy

```bash
# Ubuntu/Debian
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

#### Configure Caddy

Create `/etc/caddy/Caddyfile`:

```
your-domain.com {
    # Serve static files directly
    handle /static/* {
        root * /path/to/wine-cellar
        file_server
    }

    handle /media/* {
        root * /path/to/wine-cellar
        file_server
    }

    # Proxy everything else to Gunicorn
    handle {
        reverse_proxy localhost:8000
    }
}
```

#### Update Django Settings

Edit `.env.prod.local`:

```bash
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,your-domain.com"
DJANGO_CSRF_TRUSTED_ORIGINS="https://your-domain.com"
SITE_URL=https://your-domain.com
```

#### Start Services

```bash
# Modify run_prod_local.sh: change --bind 0.0.0.0:80 to --bind 127.0.0.1:8000
sudo systemctl enable caddy
sudo systemctl start caddy
./run_prod_local.sh start
```

### Option 2: Self-Signed Certificate (IP Address Only)

For testing without a domain name.

#### Generate Certificate

```bash
sudo mkdir -p /etc/ssl/wine-cellar
cd /etc/ssl/wine-cellar

# Replace YOUR_IP with your server's external IP
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout private.key \
    -out certificate.crt \
    -subj "/CN=YOUR_IP" \
    -addext "subjectAltName=IP:YOUR_IP"

sudo chmod 600 private.key
sudo chmod 644 certificate.crt
```

#### Configure Caddy

Create `/etc/caddy/Caddyfile`:

```
{
    auto_https off
}

:443 {
    tls /etc/ssl/wine-cellar/certificate.crt /etc/ssl/wine-cellar/private.key

    handle /static/* {
        root * /path/to/wine-cellar
        file_server
    }

    handle /media/* {
        root * /path/to/wine-cellar
        file_server
    }

    handle {
        reverse_proxy localhost:8000
    }
}

:80 {
    redir https://{host}{uri} permanent
}
```

#### Trust Certificate on Mobile

**iOS:**
1. Email or AirDrop `certificate.crt` to device
2. Install the profile
3. Go to Settings → General → About → Certificate Trust Settings
4. Enable full trust

**Android:**
1. Transfer `certificate.crt` to device
2. Go to Settings → Security → Install from storage
3. Select and install the certificate

### Option 3: Nginx with Let's Encrypt

```bash
sudo apt install nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/wine-cellar`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location /static/ {
        alias /path/to/wine-cellar/static/;
    }

    location /media/ {
        alias /path/to/wine-cellar/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and get certificate:

```bash
sudo ln -s /etc/nginx/sites-available/wine-cellar /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

---

## Email Configuration

Wine Cellar can send notification emails, including drink-by reminders.

Add to `.env.prod.local`:

```bash
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your@email.com
DJANGO_EMAIL_HOST_PASSWORD=yourpassword
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Wine Cellar <your@email.com>
```

**Note:** USE_TLS and USE_SSL are mutually exclusive.

---

## Drink-By Reminders (Cron)

Drink-by reminder emails are sent by the `send_drink_reminders` management command. You need to schedule this with a host cron job — it is **not** run automatically by the application server.

Email configuration (see above) must be set up before reminders will be delivered.

### Docker deployments

Add a cron entry on the host that runs the command inside the running container:

```
0 9 * * * docker compose -f /path/to/docker-compose.prod.yml exec -T wine-web python manage.py send_drink_reminders >> /var/log/drink_reminders.log 2>&1
```

### Non-Docker (bare-metal / virtualenv) deployments

```
0 9 * * * cd /path/to/wine-cellar && venv/bin/python manage.py send_drink_reminders >> /var/log/drink_reminders.log 2>&1
```

Adjust the time (`0 9 * * *` = 09:00 daily) to suit your timezone. The command only sends emails to users who have notifications enabled and have wines in their final drinking year, so it is safe to run daily.

---

## Systemd Service (Auto-Start)

Create `/etc/systemd/system/wine-cellar.service`:

```ini
[Unit]
Description=Wine Cellar Gunicorn Server
After=network.target

[Service]
User=your-username
Group=your-username
WorkingDirectory=/path/to/wine-cellar
Environment="PATH=/path/to/wine-cellar/venv/bin"
EnvironmentFile=/path/to/wine-cellar/.env.prod.local
ExecStart=/path/to/wine-cellar/venv/bin/gunicorn wine_cellar.conf.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wine-cellar
sudo systemctl start wine-cellar
sudo systemctl status wine-cellar
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
| `DATABASE_URL` | No | SQLite | Database connection URL |
| `ADMIN_USER` | No | admin | Initial admin username |
| `ADMIN_USER_EMAIL` | No | - | Admin email address |
| `ADMIN_USER_PASSWORD` | Yes | - | Admin password |
| `DJANGO_ENABLE_SIGNUPS` | No | False | Allow new user registrations |

---

## Security Checklist

Before going live:

- [ ] Generate a new `SECRET_KEY` (minimum 64 characters)
- [ ] Set `DJANGO_DEBUG=False`
- [ ] Use strong password for `ADMIN_USER_PASSWORD`
- [ ] Configure `DJANGO_ALLOWED_HOSTS` with only your domain/IP
- [ ] Configure `DJANGO_CSRF_TRUSTED_ORIGINS` correctly
- [ ] Set up HTTPS (using Caddy/Nginx as reverse proxy)
- [ ] Configure firewall to allow only necessary ports
- [ ] Review and restrict `DJANGO_ENABLE_SIGNUPS`
- [ ] Set up regular database backups
- [ ] Use PostgreSQL for production (not SQLite)

---

## Troubleshooting

### Connection Refused

**Check firewall rules:**
```bash
# GCP example
gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags=http-server
```

**Check server is running:**
```bash
./run_prod_local.sh status
sudo systemctl status wine-cellar
```

**Check logs:**
```bash
./run_prod_local.sh logs
journalctl -u wine-cellar -f
```

### DisallowedHost Error

Add your domain/IP to `DJANGO_ALLOWED_HOSTS` in `.env.prod.local`:

```bash
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,your-domain.com,your-ip"
```

Restart server:
```bash
sudo ./run_prod_local.sh restart
# or
sudo systemctl restart wine-cellar
```

### CSRF Verification Failed

Add your URL to `DJANGO_CSRF_TRUSTED_ORIGINS` (include the protocol):

```bash
DJANGO_CSRF_TRUSTED_ORIGINS="http://your-domain.com,https://your-domain.com"
```

### Static Files Not Loading

```bash
# Collect static files
python manage.py collectstatic --no-input

# Check Whitenoise is configured in settings
```

### Camera Not Working (Mobile)

1. Ensure you're using HTTPS (required for camera access)
2. Check browser permissions for camera
3. Try accessing via `./run_https.sh` for development
4. For production, use Caddy or Nginx with SSL

### Useful Commands

```bash
# Enter Django shell
source venv/bin/activate
python manage.py shell

# Create new superuser
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Check server listening port
sudo netstat -tlnp | grep :8000

# Test response times
curl -s -w "time: %{time_total}s\n" -o /dev/null http://localhost:8000/
```

---

## Performance Tuning

For optimal performance:

1. **Use PostgreSQL** instead of SQLite in production
2. **Enable caching** with Redis
3. **Use a CDN** for static files
4. **Increase Gunicorn workers**: `--workers $(( 2 * $(nproc) + 1 ))`
5. **Enable compression** (WhiteNoise handles this automatically)

---

## Notes

- **Port 80 requires sudo** - Running on port 80 requires root privileges
- **SQLite for simplicity** - Fine for personal use, PostgreSQL recommended for production
- **Static files** - Served by WhiteNoise middleware
- **Background tasks** - Celery requires Redis configuration

---

For more details, see:
- [Environment Variables](environment.md)
- [Setup Guide](setup.md)
- [Backup & Restore](backup.md)
