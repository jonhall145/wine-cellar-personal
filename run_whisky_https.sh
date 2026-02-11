#!/bin/bash
set -e

# Whisky Cellar - HTTPS Development Server
# Uses django-extensions runserver_plus with SSL
# Usage: ./run_whisky_https.sh [--collect-static]

cd "$(dirname "$0")"

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

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f .env.dev ]; then
    set -a
    source .env.dev
    set +a
fi

# Ensure DEBUG is on for development (overrides default False in settings.py)
export DJANGO_DEBUG=True

# Set app type to whisky
export CELLAR_APP_TYPE=whisky

# Detect meshnet IP (typically in 100.64.0.0/10 range)
MESHNET_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)100\.\d+\.\d+\.\d+' | head -n1)
LOCAL_IP=$(hostname -I | awk '{print $1}')

# Build Subject Alternative Names
SAN="DNS:localhost,IP:127.0.0.1,IP:0.0.0.0"
if [ -n "$LOCAL_IP" ]; then
    SAN="$SAN,IP:$LOCAL_IP"
fi
if [ -n "$MESHNET_IP" ]; then
    SAN="$SAN,IP:$MESHNET_IP"
fi

# Check SSL certificates exist
if [ ! -f ssl/server.crt ] || [ ! -f ssl/server.key ]; then
    echo "SSL certificates not found. Generating..."
    mkdir -p ssl
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/server.key \
        -out ssl/server.crt \
        -subj "/C=US/ST=State/L=City/O=WhiskyCellar/CN=localhost" \
        -addext "subjectAltName=$SAN"
    echo "SSL certificates generated with SANs: $SAN"
else
    echo "Existing SSL certificates found."
fi

echo "=========================================="
echo "Whisky Cellar - HTTPS Development Server"
echo "=========================================="
echo ""
echo "Starting HTTPS server..."
echo ""
echo "Access at:"
echo "  Local:   https://localhost:8001"
if [ -n "$LOCAL_IP" ]; then
    echo "  LAN:     https://$LOCAL_IP:8001"
fi
if [ -n "$MESHNET_IP" ]; then
    echo "  Meshnet: https://$MESHNET_IP:8001"
fi
echo ""
echo "NOTE: You will need to accept the self-signed certificate"
echo "      in your browser the first time you connect."
echo ""
echo "To trust on mobile devices:"
echo "  1. Navigate to the URL in your mobile browser"
echo "  2. Accept the security warning"
echo "  3. Camera access will then work"
echo ""

# Collect static files (optional - slow due to compression)
if [ "$COLLECT_STATIC" = true ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    echo ""
else
    echo "Skipping collectstatic (use --collect-static or -s to enable)"
    echo ""
fi

PORT="${PORT:-8001}"
python manage.py runserver_plus 0.0.0.0:$PORT --cert-file ssl/server.crt --key-file ssl/server.key
