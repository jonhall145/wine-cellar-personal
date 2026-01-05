# External Access Setup

Your Wine Cellar application is now configured to accept external connections, but you need to create a GCP firewall rule to allow traffic on port 8000.

## Your VM Information
- **Internal IP**: 10.128.0.2
- **External IP**: 34.71.71.2
- **Application Port**: 8000

## Configuration Already Applied

✅ **Django Settings Updated**
- `DJANGO_ALLOWED_HOSTS` now includes your external IP (34.71.71.2)
- `DJANGO_CSRF_TRUSTED_ORIGINS` configured for external access

## Required: Create GCP Firewall Rule

You need to create a firewall rule to allow incoming traffic on port 8000. You can do this in two ways:

### Option 1: Using Google Cloud Console (Web UI)

1. Go to [GCP Console - Firewall Rules](https://console.cloud.google.com/networking/firewalls/list)
2. Click **"CREATE FIREWALL RULE"**
3. Configure the rule:
   - **Name**: `allow-wine-dev`
   - **Description**: `Allow access to Wine Cellar development server on port 8000`
   - **Targets**: All instances in the network (or specific target tags if your VM has them)
   - **Source filter**: IP ranges
   - **Source IP ranges**: `0.0.0.0/0` (allow from anywhere) 
     - OR for better security, enter only your phone's IP range
   - **Protocols and ports**: 
     - Check **"Specified protocols and ports"**
     - **tcp**: `8000`
4. Click **"CREATE"**

### Option 2: Using gcloud Command (From Your Local Machine)

Run this command from your local machine (not the VM) if you have gcloud CLI installed:

```bash
gcloud compute firewall-rules create allow-wine-dev \
    --allow=tcp:8000 \
    --source-ranges=0.0.0.0/0 \
    --description="Allow access to Wine Cellar development server on port 8000"
```

For better security, restrict to your specific IP:
```bash
gcloud compute firewall-rules create allow-wine-dev \
    --allow=tcp:8000 \
    --source-ranges=YOUR_IP_ADDRESS/32 \
    --description="Allow access to Wine Cellar development server on port 8000"
```

## After Creating the Firewall Rule

### Start the Development Server
```bash
cd /home/jonhall145/wine
./run_local.sh
```

### Access URLs

Once the server is running, you can access it from:

1. **From your phone** (or any external device):
   ```
   http://34.71.71.2:8000
   ```

2. **From the VM locally**:
   ```
   http://127.0.0.1:8000
   http://10.128.0.2:8000
   ```

### Admin Interface
```
http://34.71.71.2:8000/admin/
```
- Username: `admin`
- Password: `change_me`

## Security Considerations

⚠️ **IMPORTANT SECURITY NOTES**:

1. **Development Mode**: The server is running in DEBUG mode - DO NOT use this in production
2. **Firewall**: Opening port 8000 to `0.0.0.0/0` allows anyone to access your server
3. **Default Password**: Change the admin password immediately after first login

### Recommended Security Improvements

1. **Restrict firewall to your IP only**:
   ```bash
   # Find your IP
   curl ifconfig.me
   
   # Update firewall rule to only allow your IP
   gcloud compute firewall-rules update allow-wine-dev \
       --source-ranges=YOUR_IP_ADDRESS/32
   ```

2. **Change admin password**:
   ```bash
   source venv/bin/activate
   export $(cat .env.dev | grep -v '^#' | xargs)
   python manage.py changepassword admin
   ```

3. **For production use**: Use `./run_prod_local.sh` with proper configuration

## Troubleshooting

### Can't connect from phone?

1. **Check firewall rule is created**:
   ```bash
   gcloud compute firewall-rules list | grep wine
   ```

2. **Check server is running**:
   ```bash
   ps aux | grep manage.py
   ```

3. **Check server is listening on all interfaces**:
   ```bash
   sudo netstat -tlnp | grep 8000
   ```
   Should show: `0.0.0.0:8000` (not `127.0.0.1:8000`)

4. **Test from VM**:
   ```bash
   curl http://34.71.71.2:8000
   ```

### SSL/HTTPS Warnings

The development server uses HTTP (not HTTPS). Your browser may show security warnings. This is expected for a development server.

For HTTPS, you would need to:
- Set up nginx or caddy as a reverse proxy
- Configure a domain name
- Set up SSL certificates (Caddy does this automatically with Let's Encrypt)

## Quick Commands Reference

### Start Server
```bash
./run_local.sh
```

### Stop Server
Press `CTRL+C` in the terminal where the server is running

### Check if firewall rule exists
```bash
gcloud compute firewall-rules describe allow-wine-dev
```

### Delete firewall rule (when done testing)
```bash
gcloud compute firewall-rules delete allow-wine-dev
```
