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

    # Verify database authentication works (not just port availability)
    echo "Verifying database credentials..."
    if ! python -c "
import os, sys
try:
    import psycopg
    conn = psycopg.connect(
        host=os.environ['SQL_HOST'],
        port=int(os.environ['SQL_PORT']),
        user=os.environ['SQL_USER'],
        password=os.environ['SQL_PASSWORD'],
        dbname=os.environ['SQL_DATABASE'],
    )
    conn.close()
except Exception as e:
    print(f'FATAL: Database authentication failed: {e}', file=sys.stderr)
    print('Check that POSTGRES_USER/POSTGRES_DB in the db container match SQL_USER/SQL_DATABASE in the web container.', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        exit 1
    fi
    echo "Database credentials verified"
fi

# Only run setup tasks for web server commands
if [ "$1" = "python" ] || [ "$1" = "gunicorn" ]; then
    # Run migrations
    echo "Running migrations..."
    python manage.py migrate --no-input

    # Verify no unapplied migrations remain (catches DB restore/mismatch)
    PENDING=$(python manage.py showmigrations --plan 2>/dev/null | grep '\[ \]' | wc -l)
    if [ "$PENDING" -gt 0 ]; then
        echo "WARNING: $PENDING unapplied migrations after migrate. Retrying..."
        python manage.py migrate --no-input
    fi

    # One-time cleanup: drop legacy django_celery_beat tables if they exist
    if [ "$DATABASE" = "postgres" ]; then
        python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'django_celery_beat%%'\")
    tables = [r[0] for r in c.fetchall()]
    for t in tables:
        quoted = connection.ops.quote_name(t)
        c.execute(f'DROP TABLE IF EXISTS {quoted} CASCADE')
        print(f'Dropped legacy table {t}')
" 2>/dev/null || true
    fi

    # Load initial fixture data based on app type - safe to re-run
    if [ "$CELLAR_APP_TYPE" = "whisky" ]; then
        python manage.py loaddata fixtures/whisky_regions.json 2>/dev/null || true
        python manage.py loaddata fixtures/distilleries.json 2>/dev/null || true
        python manage.py loaddata fixtures/bottlers.json 2>/dev/null || true
    else
        python manage.py loaddata fixtures/grapes.json 2>/dev/null || true
    fi

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
