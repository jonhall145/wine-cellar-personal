#!/bin/bash
set -e

# Wine Cellar - Cloudflare Tunnel Server
# Runs the app behind cloudflared for external access without VPN

PIDFILE="/tmp/wine_cellar_gunicorn_cf.pid"
LOGFILE="gunicorn_cloudflared.log"
PORT="${PORT:-8000}"
TUNNEL_NAME="${TUNNEL_NAME:-wine-cellar}"

cd "$(dirname "$0")"

show_help() {
    echo "Wine Cellar - Cloudflare Tunnel Server"
    echo ""
    echo "Usage: ./run_cloudflared.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start HTTP server (for cloudflared to proxy)"
    echo "  stop        - Stop the server"
    echo "  restart     - Restart the server"
    echo "  status      - Show server status"
    echo "  logs        - Show server logs"
    echo "  tunnel      - Start cloudflared tunnel (after server is running)"
    echo "  setup       - Show cloudflared setup instructions"
    echo "  help        - Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  PORT        - Port to listen on (default: 8000)"
    echo "  TUNNEL_NAME - Cloudflare tunnel name (default: wine-cellar)"
    echo ""
    echo "Quick start:"
    echo "  1. ./run_cloudflared.sh start    # Start the HTTP server"
    echo "  2. ./run_cloudflared.sh tunnel   # Start cloudflared tunnel"
    echo ""
}

show_setup() {
    echo "=========================================="
    echo "Cloudflare Tunnel Setup Instructions"
    echo "=========================================="
    echo ""
    echo "One-time setup (if not done already):"
    echo ""
    echo "  1. Install cloudflared:"
    echo "     curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /usr/local/bin/cloudflared"
    echo "     chmod +x /usr/local/bin/cloudflared"
    echo ""
    echo "  2. Authenticate with Cloudflare:"
    echo "     cloudflared tunnel login"
    echo ""
    echo "  3. Create a named tunnel:"
    echo "     cloudflared tunnel create $TUNNEL_NAME"
    echo ""
    echo "  4. Route DNS to the tunnel (replace YOUR_DOMAIN):"
    echo "     cloudflared tunnel route dns $TUNNEL_NAME YOUR_DOMAIN.example.com"
    echo ""
    echo "  5. Update .env.prod:"
    echo "     Replace CLOUDFLARE_DOMAIN_PLACEHOLDER with your actual domain"
    echo ""
    echo "=========================================="
}

check_requirements() {
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
}

start_server() {
    check_requirements

    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "Server is already running (PID: $(cat $PIDFILE))"
        exit 1
    fi

    echo "=========================================="
    echo "Wine Cellar - Cloudflare Tunnel Server"
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

    # Collect static files (optional)
    if [ "${BUILD_STATIC:-0}" = "1" ]; then
        echo ""
        echo "Collecting static files..."
        python manage.py collectstatic --no-input
    fi

    echo ""
    echo "Starting Gunicorn HTTP server on port $PORT..."
    echo "(cloudflared will handle HTTPS termination)"

    # Start Gunicorn in HTTP mode (no SSL - cloudflared handles that)
    nohup bash -c "
        source venv/bin/activate
        set -a
        source $ENV_FILE
        set +a
        exec venv/bin/gunicorn wine_cellar.conf.wsgi:application \
            --bind 127.0.0.1:$PORT \
            --worker-class sync \
            --workers 2 \
            --timeout 120 \
            --pid '$PIDFILE'
    " >> "$LOGFILE" 2>&1 &

    # Wait for gunicorn to start and create PID file
    for i in {1..10}; do
        if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo ""
        echo "=========================================="
        echo "HTTP Server started successfully!"
        echo "=========================================="
        echo ""
        echo "Local access: http://127.0.0.1:$PORT"
        echo ""
        echo "PID: $(cat $PIDFILE)"
        echo "Logs: $LOGFILE"
        echo ""
        echo "Next step: ./run_cloudflared.sh tunnel"
    else
        echo "Error: Failed to start server. Check logs at $LOGFILE"
        exit 1
    fi
}

start_tunnel() {
    if ! command -v cloudflared &> /dev/null; then
        echo "Error: cloudflared not found. Run: ./run_cloudflared.sh setup"
        exit 1
    fi

    # Check if server is running
    if ! [ -f "$PIDFILE" ] || ! kill -0 $(cat "$PIDFILE") 2>/dev/null; then
        echo "Warning: HTTP server not running. Start it first: ./run_cloudflared.sh start"
    fi

    echo "Starting cloudflared tunnel..."
    echo ""
    echo "If you haven't set up a named tunnel yet, run:"
    echo "  ./run_cloudflared.sh setup"
    echo ""

    # Check for existing tunnel config
    if [ -f "$HOME/.cloudflared/config.yml" ]; then
        echo "Using tunnel config from ~/.cloudflared/config.yml"
        cloudflared tunnel run
    else
        echo "No config found. Starting tunnel for $TUNNEL_NAME..."
        echo "Proxying to http://127.0.0.1:$PORT"
        cloudflared tunnel --url http://127.0.0.1:$PORT run $TUNNEL_NAME
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
        echo "HTTP Server is running (PID: $(cat $PIDFILE))"
        echo "Logs: $LOGFILE"
        echo ""
        # Check if cloudflared is running
        if pgrep -f "cloudflared tunnel" > /dev/null; then
            echo "Cloudflared tunnel is running"
        else
            echo "Cloudflared tunnel is NOT running"
            echo "Start it with: ./run_cloudflared.sh tunnel"
        fi
    else
        echo "HTTP Server is not running"
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
    tunnel)
        start_tunnel
        ;;
    setup)
        show_setup
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
