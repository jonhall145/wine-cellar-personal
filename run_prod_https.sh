#!/bin/bash
set -e

# Wine Cellar - Production HTTPS Server
# Uses Gunicorn with SSL certificates

PIDFILE="/tmp/wine_cellar_gunicorn_https.pid"
LOGFILE="gunicorn_https.log"
PORT="${PORT:-443}"

cd "$(dirname "$0")"

show_help() {
    echo "Wine Cellar - Production HTTPS Server"
    echo ""
    echo "Usage: ./run_prod_https.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start HTTPS production server"
    echo "  stop     - Stop the server"
    echo "  restart  - Restart the server"
    echo "  status   - Show server status"
    echo "  logs     - Show server logs"
    echo "  help     - Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  PORT         - Port to listen on (default: 443)"
    echo "  BUILD_STATIC - Set to 1 to rebuild static assets (default: 0)"
    echo ""
    echo "Note: Requires sudo to bind to port 443"
    echo ""
}

check_requirements() {
    # Check if running as root/sudo (required for port 443)
    if [ "${PORT:-443}" -le 1024 ] && [ "$EUID" -ne 0 ]; then
        echo "Error: This script requires sudo to bind to port ${PORT:-443}"
        echo "Run: sudo ./run_prod_https.sh $1"
        exit 1
    fi

    if [ ! -d "venv" ]; then
        echo "Error: Virtual environment not found."
        echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi

    # Check for .env.prod or .env.prod.local
    if [ -f ".env.prod" ]; then
        ENV_FILE=".env.prod"
    elif [ -f ".env.prod.local" ]; then
        ENV_FILE=".env.prod.local"
    else
        echo "Error: Neither .env.prod nor .env.prod.local found."
        echo "Create one with production settings."
        exit 1
    fi
    
    # Check/generate SSL certificates
    if [ ! -f "ssl/server.crt" ] || [ ! -f "ssl/server.key" ]; then
        echo "SSL certificates not found. Generating..."
        mkdir -p ssl
        
        # Get external IP and Nord Meshnet info
        EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "localhost")
        MESHNET_IP=$(ip addr show nord-tun 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "")
        MESHNET_HOSTNAME=$(nordvpn meshnet peer list 2>/dev/null | grep "This device:" -A 1 | grep "Hostname:" | awk '{print $2}' || echo "")

        # Build subjectAltName with available addresses
        SAN="DNS:localhost,IP:127.0.0.1,IP:0.0.0.0,IP:$EXTERNAL_IP"
        [ -n "$MESHNET_IP" ] && SAN="$SAN,IP:$MESHNET_IP"
        [ -n "$MESHNET_HOSTNAME" ] && SAN="$SAN,DNS:$MESHNET_HOSTNAME"

        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/server.key \
            -out ssl/server.crt \
            -subj "/C=US/ST=State/L=City/O=WineCellar/CN=$EXTERNAL_IP" \
            -addext "subjectAltName=$SAN"
        echo "SSL certificates generated for $EXTERNAL_IP"
        [ -n "$MESHNET_HOSTNAME" ] && echo "  - Meshnet: $MESHNET_HOSTNAME ($MESHNET_IP)"
    fi
}

start_server() {
    check_requirements
    
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "Server is already running (PID: $(cat $PIDFILE))"
        exit 1
    fi
    
    echo "=========================================="
    echo "Wine Cellar - Production HTTPS Server"
    echo "=========================================="
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Load environment variables
    echo "Using environment file: $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
    
    # Run migrations
    echo ""
    echo "Running migrations..."
    python manage.py migrate --no-input
    
    # Collect static files (optional, skipped by default)
    if [ "${BUILD_STATIC:-0}" = "1" ]; then
        echo ""
        echo "Collecting static files..."
        python manage.py collectstatic --no-input
    fi
    
    # Get external IP and Meshnet info
    EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || echo "your-server-ip")
    MESHNET_HOSTNAME=$(nordvpn meshnet peer list 2>/dev/null | grep "This device:" -A 1 | grep "Hostname:" | awk '{print $2}' || echo "")

    echo ""
    echo "Starting Gunicorn with HTTPS on port $PORT..."
    
    # Start Gunicorn with SSL in background
    # Load environment and run gunicorn without daemon mode, using nohup instead
    nohup bash -c "
        source venv/bin/activate
        set -a
        source $ENV_FILE
        set +a
        exec venv/bin/gunicorn wine_cellar.conf.wsgi:application \
            --bind 0.0.0.0:$PORT \
            --worker-class sync \
            --workers 2 \
            --timeout 120 \
            --certfile ssl/server.crt \
            --keyfile ssl/server.key \
            --pid '$PIDFILE'
    " >> "$LOGFILE" 2>&1 &
    
    # Save the PID manually since --daemon doesn't work with bash wrapper
    echo $! > /tmp/wine_cellar_wrapper.pid
    
    # Wait for gunicorn to start and create PID file
    for i in {1..10}; do
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            break
        fi
        sleep 1
    done
    
    # Check if PID file was created by gunicorn
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "Server started successfully!"
        echo "=========================================="
        echo ""
        if [ "$PORT" = "443" ]; then
            echo "Access your site at: https://${EXTERNAL_IP}"
            echo "Admin panel at: https://${EXTERNAL_IP}/admin/"
            if [ -n "$MESHNET_HOSTNAME" ]; then
                echo ""
                echo "Nord Meshnet access:"
                echo "  https://${MESHNET_HOSTNAME}"
                echo "  https://${MESHNET_HOSTNAME}/admin/"
            fi
        else
            echo "Access your site at: https://${EXTERNAL_IP}:${PORT}"
            echo "Admin panel at: https://${EXTERNAL_IP}:${PORT}/admin/"
            if [ -n "$MESHNET_HOSTNAME" ]; then
                echo ""
                echo "Nord Meshnet access:"
                echo "  https://${MESHNET_HOSTNAME}:${PORT}"
                echo "  https://${MESHNET_HOSTNAME}:${PORT}/admin/"
            fi
        fi
        echo ""
        echo "NOTE: Accept the self-signed certificate warning in your browser."
        echo ""
        echo "PID: $(cat $PIDFILE)"
        echo "Logs: $LOGFILE"
        echo ""
        echo "To stop: ./run_prod_https.sh stop"
        echo "To view logs: ./run_prod_https.sh logs"
    else
        echo "Error: Failed to start server. Check logs at $LOGFILE"
        exit 1
    fi
}

stop_server() {
    if [ -f "$PIDFILE" ]; then
        PID=$(cat "$PIDFILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping server (PID: $PID)..."
            kill "$PID"
            rm -f "$PIDFILE"
            echo "Server stopped."
        else
            echo "Server not running (stale PID file)"
            rm -f "$PIDFILE"
        fi
    else
        echo "Server not running (no PID file)"
    fi
}

show_status() {
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "Server is running (PID: $(cat $PIDFILE))"
        echo "Logs: $LOGFILE"
    else
        echo "Server is not running"
    fi
}

show_logs() {
    if [ -f "$LOGFILE" ]; then
        tail -f "$LOGFILE"
    else
        echo "No log file found at $LOGFILE"
    fi
}

case "${1:-help}" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 2
        start_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
