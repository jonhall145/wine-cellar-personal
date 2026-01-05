# Troubleshooting Connection Refused Error

## Current Status

✅ **Server is running correctly**
- URL: http://34.71.71.2:8000
- Admin: http://34.71.71.2:8000/admin/
- Server logs show requests are being processed successfully

✅ **Configuration Fixed**
- `SITE_URL` updated to use external IP: http://34.71.71.2:8000
- `ALLOWED_HOSTS` includes: 0.0.0.0, localhost, 127.0.0.1, 10.128.0.2, 34.71.71.2
- `CSRF_TRUSTED_ORIGINS` includes all necessary URLs

## Common Causes of "Connection Refused" After Login

### 1. **GCP Firewall Rule Not Created** (MOST LIKELY)
If you haven't created the firewall rule yet, external connections will be blocked.

**Solution:**
1. Go to: https://console.cloud.google.com/networking/firewalls/list
2. Click "CREATE FIREWALL RULE"
3. Set:
   - Name: `allow-wine-dev`
   - Protocols and ports: **tcp:8000**
   - Source IP ranges: `0.0.0.0/0`
4. Click CREATE

### 2. **Browser Cache/Redirect Issue**
Your browser might have cached an old redirect or URL.

**Solution:**
- Clear browser cache and cookies
- Try incognito/private browsing mode
- Hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
- Try from a different browser

### 3. **Mixed HTTP/HTTPS**
Some browsers automatically try to upgrade HTTP to HTTPS, which will fail.

**Solution:**
- Make sure you're accessing `http://` (not `https://`)
- In Chrome, you might need to type `http://` explicitly
- Check if your browser is forcing HTTPS upgrades

### 4. **Port in URL**
After login, the redirect might be stripping the `:8000` port.

**Check:**
- Look at the URL bar after clicking "login" - does it still show `:8000`?
- If not, there might be a redirect issue

## Verification Steps

### 1. Test from the VM itself
```bash
curl -I http://34.71.71.2:8000
curl -I http://34.71.71.2:8000/admin/
```
Both should return `HTTP/1.1 302 Found` or `HTTP/1.1 200 OK`

### 2. Check if firewall rule exists
```bash
gcloud compute firewall-rules describe allow-wine-dev
```
If this returns an error, the rule doesn't exist yet.

### 3. Test from your phone's browser
1. Make sure you're on mobile data (not your home network)
2. Navigate to: `http://34.71.71.2:8000`
3. Check browser console for errors (if using Chrome on Android)

### 4. Check server logs
```bash
tail -f /tmp/server.log
```
Then try to access the site - you should see log entries appear

## What "Connection Refused" Means

- **Connection Refused**: The request reached the server but was actively rejected (usually firewall)
- **Connection Timeout**: The request never reached the server (network issue)
- **404 Not Found**: Server received request but page doesn't exist
- **302 Redirect**: Server is redirecting you (this is normal for login)

## Current Server Status

Check if server is running:
```bash
ps aux | grep "manage.py runserver" | grep -v grep
```

Check what port is listening:
```bash
sudo netstat -tlnp | grep :8000
```
Should show: `0.0.0.0:8000` (not `127.0.0.1:8000`)

## Debug Mode

If you want to see detailed error messages, the server is already in DEBUG mode. Check `/tmp/server.log` for any errors.

## Most Likely Solution

**Create the GCP firewall rule!** This is the #1 reason for connection refused errors. The server is running and configured correctly, but GCP is blocking incoming connections.

After creating the firewall rule, wait 1-2 minutes for it to propagate, then try again.

## Still Not Working?

1. **Verify firewall rule:**
   ```bash
   gcloud compute firewall-rules list | grep wine
   ```

2. **Check if any error in logs:**
   ```bash
   tail -50 /tmp/server.log
   ```

3. **Try from the VM's internal IP:**
   From your phone (on the same network): `http://10.128.0.2:8000`

4. **Restart the server:**
   ```bash
   # Kill existing server
   kill $(ps aux | grep 'manage.py runserver' | grep -v grep | awk '{print $2}')
   
   # Start fresh
   ./run_local.sh > /tmp/server.log 2>&1 &
   ```

## Alternative: Test with ngrok (temporary)

If you want to test immediately without waiting for GCP firewall:
```bash
# Install ngrok (if not installed)
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Create tunnel to port 8000
ngrok http 8000
```

This will give you a temporary public URL (like https://abc123.ngrok.io) you can use for testing.
