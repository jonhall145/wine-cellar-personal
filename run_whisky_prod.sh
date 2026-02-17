#!/bin/bash
set -e

# Whisky Cellar - Production Server Manager
#
# Manages the whisky production gunicorn instance:
#   cloudflared  - HTTP on 127.0.0.1:8004 (behind Cloudflare tunnel for whisky.jonandem.com)
#
# Usage:
#   ./run_whisky_prod.sh start     Start the server
#   ./run_whisky_prod.sh stop      Stop the server
#   ./run_whisky_prod.sh restart   Restart the server
#   ./run_whisky_prod.sh status    Show status
#   ./run_whisky_prod.sh logs      Tail logs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Instance configuration ---

PID_FILE="/tmp/whisky_cellar_gunicorn_cf.pid"
LOG_FILE="gunicorn_whisky_cloudflared.log"
BIND_ADDR="127.0.0.1:8004"
ENV_FILE=".env.whisky.prod"

# --- Colors ---

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Helpers ---

show_help() {
    echo "Whisky Cellar - Production Server Manager"
    echo ""
    echo "Usage: ./run_whisky_prod.sh <command>"
    echo ""
    echo "Commands:"
    echo "  start     Start the server (127.0.0.1:8004 for Cloudflare tunnel)"
    echo "  stop      Stop the server"
    echo "  restart   Restart the server"
    echo "  status    Show server status"
    echo "  logs      Tail log file"
    echo "  help      Show this help message"
    echo ""
}

is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

run_setup() {
    if [ ! -d "venv" ]; then
        echo -e "${RED}Error: Virtual environment not found.${NC}"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        echo -e "${RED}Error: $ENV_FILE not found.${NC}"
        exit 1
    fi

    source venv/bin/activate
    set -a
    source "$ENV_FILE"
    set +a

    echo "Running migrations..."
    python manage.py migrate --no-input

    echo "Loading whisky fixtures..."
    python manage.py loaddata fixtures/whisky_regions.json 2>/dev/null || true
    python manage.py loaddata fixtures/distilleries.json 2>/dev/null || true
    python manage.py loaddata fixtures/bottlers.json 2>/dev/null || true

    echo "Ensuring superuser exists..."
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
}

# --- Core operations ---

do_start() {
    echo ""
    echo "Starting Whisky Cellar production server..."
    echo ""

    if is_running; then
        echo -e "  ${YELLOW}Already running${NC} (PID: $(cat "$PID_FILE"))"
        return
    fi

    run_setup
    echo ""

    nohup bash -c "
        source venv/bin/activate
        set -a
        source $ENV_FILE
        set +a
        exec venv/bin/gunicorn wine_cellar.conf.wsgi:application \
            --bind $BIND_ADDR \
            --worker-class sync \
            --workers 2 \
            --timeout 120 \
            --pid '$PID_FILE'
    " >> "$LOG_FILE" 2>&1 &

    # Wait for gunicorn to create PID file
    for _ in {1..10}; do
        if is_running; then
            break
        fi
        sleep 1
    done

    if is_running; then
        echo -e "  ${GREEN}Started${NC} (PID: $(cat "$PID_FILE"), bind: $BIND_ADDR)"
    else
        echo -e "  ${RED}Failed to start.${NC} Check $LOG_FILE"
        return 1
    fi
    echo ""
}

do_stop() {
    echo ""
    echo "Stopping Whisky Cellar production server..."
    echo ""

    if [ ! -f "$PID_FILE" ]; then
        echo -e "  ${YELLOW}Not running${NC} (no PID file)"
        echo ""
        return
    fi

    local pid
    pid=$(cat "$PID_FILE")

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        for _ in {1..10}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        rm -f "$PID_FILE"
        echo -e "  ${GREEN}Stopped${NC} (was PID: $pid)"
    else
        rm -f "$PID_FILE"
        echo -e "  ${YELLOW}Not running${NC} (stale PID file removed)"
    fi
    echo ""
}

do_restart() {
    do_stop
    sleep 2
    do_start
}

do_status() {
    echo ""
    echo "Whisky Cellar - Production Server Status"
    echo "========================================="
    echo ""

    if is_running; then
        local pid
        pid=$(cat "$PID_FILE")
        printf "  %-14s ${GREEN}running${NC}  PID: %-8s bind: %s\n" "cloudflared" "$pid" "$BIND_ADDR"
    else
        printf "  %-14s ${RED}stopped${NC}\n" "cloudflared"
    fi
    echo ""
}

do_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo "Tailing: $LOG_FILE"
        tail -f "$LOG_FILE"
    else
        echo "No log file found."
    fi
}

# --- Main ---

COMMAND="${1:-help}"

case "$COMMAND" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_restart
        ;;
    status)
        do_status
        ;;
    logs)
        do_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $COMMAND"
        show_help
        exit 1
        ;;
esac
