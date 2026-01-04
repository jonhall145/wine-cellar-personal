#!/bin/bash
set -e

# Wine Cellar - HTTPS Development Server
# Uses django-extensions runserver_plus with SSL

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f .env.dev ]; then
    set -a
    source .env.dev
    set +a
fi

# Check SSL certificates exist
if [ ! -f ssl/server.crt ] || [ ! -f ssl/server.key ]; then
    echo "SSL certificates not found. Generating..."
    mkdir -p ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/server.key \
        -out ssl/server.crt \
        -subj "/C=US/ST=State/L=City/O=WineCellar/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:0.0.0.0"
    echo "SSL certificates generated."
fi

echo "=========================================="
echo "Wine Cellar - HTTPS Development Server"
echo "=========================================="
echo ""
echo "Starting HTTPS server..."
echo ""
echo "Access at: https://localhost:8000"
echo "           https://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "NOTE: You will need to accept the self-signed certificate"
echo "      in your browser the first time you connect."
echo ""
echo "To trust on mobile devices:"
echo "  1. Navigate to the URL in your mobile browser"
echo "  2. Accept the security warning"
echo "  3. Camera access will then work"
echo ""

python manage.py runserver_plus 0.0.0.0:8000 --cert-file ssl/server.crt --key-file ssl/server.key
