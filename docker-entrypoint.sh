#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
if [ "$DATABASE" = "postgres" ]; then
    echo "Waiting for PostgreSQL at ${SQL_HOST}:${SQL_PORT}..."
    while ! python -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('${SQL_HOST}', int('${SQL_PORT}')))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
        sleep 1
    done
    echo "PostgreSQL is up"
fi

# Only run setup tasks for web server commands (not celery workers)
if [ "$1" = "python" ] || [ "$1" = "gunicorn" ]; then
    # Run migrations
    echo "Running migrations..."
    python manage.py migrate --no-input

    # Load initial fixture data (grapes) - safe to re-run
    python manage.py loaddata fixtures/grapes.json 2>/dev/null || true

    # Create superuser if configured
    if [ -n "$ADMIN_USER" ] && [ -n "$ADMIN_USER_PASSWORD" ]; then
        python manage.py shell << 'PYEOF'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
username = os.environ.get('ADMIN_USER', 'admin')
email = os.environ.get('ADMIN_USER_EMAIL', 'admin@example.org')
password = os.environ.get('ADMIN_USER_PASSWORD', 'change_me')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f'Superuser "{username}" created')
else:
    print(f'Superuser "{username}" already exists')
PYEOF
    fi

    # Collect static files when running gunicorn (production)
    if [ "$1" = "gunicorn" ]; then
        echo "Collecting static files..."
        python manage.py collectstatic --noinput
    fi
fi

exec "$@"
