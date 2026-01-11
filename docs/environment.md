# Environment Variables

This document lists all environment variables used by Wine Cellar.

## Required for Production

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | dev-only key | Django secret key for cryptographic signing. Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_DEBUG` | No | `True` | Set to `False` for production |
| `DJANGO_ALLOWED_HOSTS` | Yes (prod) | `localhost,127.0.0.1` | Comma-separated list of allowed hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Yes (prod) | `http://127.0.0.1:8000` | Comma-separated list of trusted origins for CSRF |

## Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | SQLite | Database connection URL (e.g., `postgres://user:pass@host:5432/dbname`) |

## External Services

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | No | Empty | API key for Claude vision-based wine label extraction |
| `SITE_URL` | No | `http://127.0.0.1:8000` | Base URL for emails and external links |

## Email (Production)

For production, configure a real email backend:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `EMAIL_HOST` | No | - | SMTP server hostname |
| `EMAIL_PORT` | No | `587` | SMTP server port |
| `EMAIL_HOST_USER` | No | - | SMTP username |
| `EMAIL_HOST_PASSWORD` | No | - | SMTP password |
| `EMAIL_USE_TLS` | No | `True` | Use TLS for SMTP connection |
| `DEFAULT_FROM_EMAIL` | No | - | Default sender email address |

## Celery (Background Tasks)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CELERY_BROKER_URL` | No | - | Message broker URL (e.g., `redis://localhost:6379/0`) |
| `CELERY_RESULT_BACKEND` | No | - | Result backend URL |

## Logging

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Logging level for wine_cellar app (DEBUG, INFO, WARNING, ERROR) |

## Example .env File

```bash
# Development
SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
ANTHROPIC_API_KEY=sk-ant-...

# Production
SECRET_KEY=your-production-secret-key
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=winecellar.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://winecellar.example.com
SITE_URL=https://winecellar.example.com

# Database (production)
DATABASE_URL=postgres://winecellar:password@localhost:5432/winecellar

# Email (production)
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=winecellar@example.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=Wine Cellar <noreply@example.com>

# Celery (production)
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Security Notes

- Never commit `.env` files to version control
- Use strong, unique values for `SECRET_KEY` in production
- Rotate credentials regularly
- Use environment-specific configuration files
