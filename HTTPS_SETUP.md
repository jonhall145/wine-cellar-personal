# HTTPS Setup for Non-Docker Production Server

This guide covers setting up HTTPS for the Wine Cellar application without Docker, enabling mobile camera access for the barcode scanner.

## Why HTTPS is Required

Browsers require HTTPS (secure context) to access the camera via `getUserMedia()`. Without HTTPS, the barcode scanner will fail on mobile devices with a "Camera access denied" or "NotAllowedError" message.

---

## Prerequisites

- Ubuntu/Debian-based Linux VM (GCP, AWS, etc.)
- Domain name pointing to your server (recommended) OR
- Self-signed certificate for IP-only access (testing)
- Python 3.11+ with virtual environment set up
- Port 80 and 443 open in firewall

---

## Option 1: Caddy with Domain Name (Recommended)

Caddy automatically obtains and renews Let's Encrypt certificates.

### Step 1: Install Caddy

```bash
# Install Caddy on Ubuntu/Debian
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Step 2: Configure Caddy

Create/edit `/etc/caddy/Caddyfile`:

```
your-domain.com {
    # Serve static files directly
    handle /static/* {
        root * /home/jonhall145/wine
        file_server
    }
    
    handle /media/* {
        root * /home/jonhall145/wine
        file_server
    }
    
    # Proxy everything else to Gunicorn
    handle {
        reverse_proxy localhost:8000
    }
}
```

### Step 3: Update Django Settings

Edit `.env.prod.local`:

```bash
DJANGO_DEBUG=False
SECRET_KEY=<your-secure-64-char-key>
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,your-domain.com"
DJANGO_CSRF_TRUSTED_ORIGINS="https://your-domain.com"
SITE_URL=https://your-domain.com
SQL_ENGINE=django.db.backends.sqlite3
SQL_DATABASE=db.sqlite3
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
ADMIN_USER=admin
ADMIN_USER_EMAIL=your-email@example.com
ADMIN_USER_PASSWORD=<strong-password>
```

### Step 4: Start Services

```bash
# Start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy

# Start Gunicorn on port 8000 (not 80)
# Edit run_prod_local.sh: change --bind 0.0.0.0:80 to --bind 127.0.0.1:8000
./run_prod_local.sh start
```

### Step 5: Configure GCP Firewall

```bash
# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags=http-server \
    --description="Allow HTTPS traffic"

# Optionally keep HTTP for redirect
gcloud compute firewall-rules create allow-http \
    --allow tcp:80 \
    --target-tags=http-server \
    --description="Allow HTTP traffic for HTTPS redirect"
```

---

## Option 2: Self-Signed Certificate (IP Address Only)

Use this for testing when you don't have a domain name.

### Step 1: Generate Self-Signed Certificate

```bash
# Create directory for certificates
sudo mkdir -p /etc/ssl/wine-cellar
cd /etc/ssl/wine-cellar

# Generate private key and self-signed certificate
# Replace YOUR_IP with your server's external IP
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout private.key \
    -out certificate.crt \
    -subj "/CN=YOUR_IP" \
    -addext "subjectAltName=IP:YOUR_IP"

# Set permissions
sudo chmod 600 private.key
sudo chmod 644 certificate.crt
```

### Step 2: Install and Configure Caddy

Create `/etc/caddy/Caddyfile`:

```
{
    # Disable automatic HTTPS (we're using self-signed)
    auto_https off
}

:443 {
    tls /etc/ssl/wine-cellar/certificate.crt /etc/ssl/wine-cellar/private.key
    
    handle /static/* {
        root * /home/jonhall145/wine
        file_server
    }
    
    handle /media/* {
        root * /home/jonhall145/wine
        file_server
    }
    
    handle {
        reverse_proxy localhost:8000
    }
}

# Redirect HTTP to HTTPS
:80 {
    redir https://{host}{uri} permanent
}
```

### Step 3: Update Django Settings

Edit `.env.prod.local`:

```bash
DJANGO_DEBUG=False
SECRET_KEY=<your-secure-64-char-key>
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,YOUR_IP"
DJANGO_CSRF_TRUSTED_ORIGINS="https://YOUR_IP"
SITE_URL=https://YOUR_IP
SQL_ENGINE=django.db.backends.sqlite3
SQL_DATABASE=db.sqlite3
DJANGO_SETTINGS_MODULE=wine_cellar.conf.settings
ADMIN_USER=admin
ADMIN_USER_EMAIL=your-email@example.com
ADMIN_USER_PASSWORD=<strong-password>
```

### Step 4: Modify run_prod_local.sh

Edit `run_prod_local.sh` to bind Gunicorn to localhost only (Caddy will proxy):

```bash
# Change this line:
nohup venv/bin/gunicorn wine_cellar.conf.wsgi:application \
    --bind 0.0.0.0:80 \

# To:
nohup venv/bin/gunicorn wine_cellar.conf.wsgi:application \
    --bind 127.0.0.1:8000 \
```

### Step 5: Start Services

```bash
# Start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy

# Start Gunicorn (no sudo needed for port 8000)
./run_prod_local.sh start

# Verify both are running
sudo systemctl status caddy
./run_prod_local.sh status
```

### Step 6: Configure GCP Firewall

```bash
# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https \
    --allow tcp:443 \
    --target-tags=http-server \
    --description="Allow HTTPS traffic"
```

### Step 7: Trust Certificate on Mobile Device

For self-signed certificates, you must install the certificate on your mobile device:

#### iOS:
1. Email or AirDrop the `certificate.crt` file to your device
2. Open it and follow prompts to install the profile
3. Go to Settings → General → About → Certificate Trust Settings
4. Enable full trust for the certificate

#### Android:
1. Transfer `certificate.crt` to your device
2. Go to Settings → Security → Install from storage
3. Select the certificate file and install

---

## Option 3: Nginx with Let's Encrypt (Alternative)

If you prefer Nginx over Caddy:

### Step 1: Install Nginx and Certbot

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

### Step 2: Configure Nginx

Create `/etc/nginx/sites-available/wine-cellar`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location /static/ {
        alias /home/jonhall145/wine/static/;
    }
    
    location /media/ {
        alias /home/jonhall145/wine/media/;
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

### Step 3: Enable Site and Get Certificate

```bash
sudo ln -s /etc/nginx/sites-available/wine-cellar /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo certbot --nginx -d your-domain.com
sudo systemctl restart nginx
```

---

## Systemd Service for Gunicorn

For automatic startup on boot, create `/etc/systemd/system/wine-cellar.service`:

```ini
[Unit]
Description=Wine Cellar Gunicorn Server
After=network.target

[Service]
User=jonhall145
Group=jonhall145
WorkingDirectory=/home/jonhall145/wine
Environment="PATH=/home/jonhall145/wine/venv/bin"
EnvironmentFile=/home/jonhall145/wine/.env.prod.local
ExecStart=/home/jonhall145/wine/venv/bin/gunicorn wine_cellar.conf.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wine-cellar
sudo systemctl start wine-cellar
```

---

## Verification

### Test HTTPS is Working

```bash
# From server
curl -k https://localhost/health/

# From anywhere (with domain)
curl https://your-domain.com/health/
```

### Test Camera Access

1. Open `https://your-domain.com/wine/scan/` on your mobile device
2. You should see a camera permission prompt
3. Allow camera access
4. The barcode scanner should now work

### Common Issues

**Certificate not trusted (self-signed):**
- Install the certificate on your mobile device (see Step 7 above)
- On Chrome mobile, you may need to type "thisisunsafe" to bypass the warning

**Camera still not working:**
- Check browser console for errors
- Ensure you're accessing via HTTPS, not HTTP
- Try a different browser (Chrome recommended)
- Clear browser cache and try again

**502 Bad Gateway:**
- Gunicorn is not running: `./run_prod_local.sh status`
- Check Gunicorn logs: `./run_prod_local.sh logs`

**Connection refused:**
- Check firewall rules allow port 443
- Check Caddy/Nginx is running: `sudo systemctl status caddy`

---

## Quick Reference

| Component | Port | Purpose |
|-----------|------|---------|
| Caddy/Nginx | 80 | HTTP → HTTPS redirect |
| Caddy/Nginx | 443 | HTTPS termination |
| Gunicorn | 8000 | Django application |

### Start Everything

```bash
# Start reverse proxy
sudo systemctl start caddy  # or nginx

# Start Django
./run_prod_local.sh start

# Or if using systemd
sudo systemctl start wine-cellar
```

### Stop Everything

```bash
sudo systemctl stop caddy  # or nginx
./run_prod_local.sh stop   # or sudo systemctl stop wine-cellar
```
