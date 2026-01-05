# Deployment

## Running from Source

### Development Mode

1. Copy the development environment configuration:
   ```sh
   cp .env.dev-sample .env.dev
   ```

2. Install dependencies:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   npm install
   npm run build
   ```

3. Start the development server:
   ```sh
   ./run_local.sh
   ```

Access at: http://localhost:8000

---

### Production Setup

#### Prerequisites

- Python 3.11+
- Node.js 20+

#### Steps

1. Install production dependencies:
   ```sh
   source venv/bin/activate
   pip install -r requirements/prod.txt
   pip install gunicorn
   npm install
   npm run build:prod
   ```

2. Create production environment file:
   ```sh
   # Create .env.prod.local with your settings
   ```

3. Start the production server:
   ```sh
   sudo ./run_prod_local.sh start
   ```

See `DEPLOYMENT.md` in the project root for detailed configuration options.

---

### Email Setup

Wine Cellar can send notification emails, including reminders for when a wine should be drunk by ("drink by" reminders).

To enable email notifications, configure the email backend in your environment file:

```
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=your@email.com
DJANGO_EMAIL_HOST_PASSWORD=yourpassword
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Wine Cellar <your@email.com>
```

!!! Note
    USE_TLS and USE_SSL are mutually exclusive - only one can be True.
