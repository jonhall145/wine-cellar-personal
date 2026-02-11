#!/bin/bash
set -e

# Whisky Cellar - Local Development Server
# Usage: ./run_whisky_local.sh [--collect-static]

COLLECT_STATIC=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --collect-static|-s)
            COLLECT_STATIC=true
            shift
            ;;
    esac
done

echo "=========================================="
echo "Whisky Cellar - Development Server"
echo "=========================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found."
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if .env.dev exists
if [ ! -f ".env.dev" ]; then
    echo "Error: .env.dev not found."
    echo "Run: cp .env.dev-sample .env.dev"
    exit 1
fi

# Load environment variables
set -a
source .env.dev
set +a

# Ensure DEBUG is on for development (overrides default False in settings.py)
export DJANGO_DEBUG=True

# Set app type to whisky
export CELLAR_APP_TYPE=whisky

# Run migrations
echo ""
echo "Running migrations..."
python manage.py migrate

# Create superuser if it doesn't exist
echo ""
echo "Ensuring superuser exists..."
python manage.py shell << PYEOF
from django.contrib.auth import get_user_model
import os
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

# Collect static files (optional - slow due to compression)
if [ "$COLLECT_STATIC" = true ]; then
    echo ""
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
else
    echo ""
    echo "Skipping collectstatic (use --collect-static or -s to enable)"
fi

# Get external IP if available
EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || echo "")

echo ""
echo "=========================================="
echo "Starting development server..."
echo "=========================================="
echo ""
echo "Local access:    http://127.0.0.1:8004"
if [ -n "$EXTERNAL_IP" ]; then
    echo "External access: http://${EXTERNAL_IP}:8004"
fi
echo ""
echo "Admin credentials:"
echo "  Username: ${ADMIN_USER:-admin}"
echo "  Password: ${ADMIN_USER_PASSWORD:-change_me}"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

python manage.py runserver 0.0.0.0:8004
