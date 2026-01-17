#!/bin/bash
set -e

# Wine Cellar - Production Server (No Docker)
# Usage: ./run_prod_local.sh [start|stop|status]

PIDFILE="/tmp/wine_cellar_gunicorn.pid"
LOGFILE="gunicorn.log"

show_help() {
    echo "Wine Cellar - Production Server (No Docker)"
    echo ""
    echo "Usage: ./run_prod_local.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start production server with Gunicorn"
    echo "  stop     - Stop the production server"
    echo "  restart  - Restart the production server"
    echo "  status   - Show server status"
    echo "  logs     - Show server logs"
    echo "  help     - Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  BUILD_STATIC - Set to 1 to rebuild static assets (default: 0)"
    echo ""
}

check_requirements() {
    if [ ! -d "venv" ]; then
        echo "Error: Virtual environment not found."
        echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
    
    if [ ! -f ".env.prod.local" ]; then
        echo "Error: .env.prod.local not found."
        echo "Create it with production settings."
        exit 1
    fi
}

start_server() {
    check_requirements
    
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "Server is already running (PID: $(cat $PIDFILE))"
        exit 1
    fi
    
    echo "=========================================="
    echo "Wine Cellar - Production Server (No Docker)"
    echo "=========================================="
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Load environment variables
    set -a
    source .env.prod.local
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
    
    # Create superuser if needed
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

    # Get external IP
    EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || echo "your-server-ip")

    echo ""
    echo "Starting Gunicorn..."
    
    # Start Gunicorn in background
    # Load environment and run gunicorn without daemon mode, using nohup instead
    nohup bash -c "
        source venv/bin/activate
        set -a
        source .env.prod.local
        set +a
        exec venv/bin/gunicorn wine_cellar.conf.wsgi:application \
            --bind 0.0.0.0:80 \
            --worker-class sync \
            --workers 2 \
            --timeout 120 \
            --pid '$PIDFILE'
    " >> "$LOGFILE" 2>&1 &
    
    # Save the PID manually since --daemon doesn't work with bash wrapper
    echo $! > /tmp/wine_cellar_wrapper.pid
    
    sleep 3
    
    # Check if PID file was created by gunicorn
    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "Server started successfully!"
        echo "=========================================="
        echo ""
        echo "Access your site at: http://${EXTERNAL_IP}"
        echo "Admin panel at: http://${EXTERNAL_IP}/admin/"
        echo ""
        echo "PID: $(cat $PIDFILE)"
        echo "Logs: $LOGFILE"
        echo ""
        echo "To stop: ./run_prod_local.sh stop"
        echo "To view logs: ./run_prod_local.sh logs"
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
