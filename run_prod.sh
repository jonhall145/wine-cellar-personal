#!/bin/bash
set -e

# Wine Cellar - Unified Production Server Manager
#
# Manages all production gunicorn instances:
#   cloudflared  - HTTP on 127.0.0.1:8000 (behind Cloudflare tunnel for jonandem.com)
#   http         - HTTP on 0.0.0.0:80 (direct LAN access)
#   https        - HTTPS on 0.0.0.0:443 (NordVPN meshnet access, self-signed cert)
#
# Usage:
#   ./run_prod.sh start [instance]     Start instance(s)
#   ./run_prod.sh stop [instance]      Stop instance(s)
#   ./run_prod.sh restart [instance]   Restart instance(s)
#   ./run_prod.sh status               Show status of all instances
#   ./run_prod.sh logs [instance]      Tail logs
#
# Instance can be: cloudflared, http, https, all
# If omitted, operates on all currently running instances (or all for start/status).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Instance configuration ---

declare -A PID_FILES=(
    [cloudflared]="/tmp/wine_cellar_gunicorn_cf.pid"
    [http]="/tmp/wine_cellar_gunicorn.pid"
    [https]="/tmp/wine_cellar_gunicorn_https.pid"
)

declare -A LOG_FILES=(
    [cloudflared]="gunicorn_cloudflared.log"
    [http]="gunicorn.log"
    [https]="gunicorn_https.log"
)

declare -A BIND_ADDRS=(
    [cloudflared]="127.0.0.1:8000"
    [http]="0.0.0.0:80"
    [https]="0.0.0.0:443"
)

ALL_INSTANCES=(cloudflared http https)

# --- Colors ---

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Helpers ---

show_help() {
    echo "Wine Cellar - Unified Production Server Manager"
    echo ""
    echo "Usage: ./run_prod.sh <command> [instance]"
    echo ""
    echo "Commands:"
    echo "  start [instance]    Start instance(s)"
    echo "  stop [instance]     Stop instance(s)"
    echo "  restart [instance]  Restart instance(s)"
    echo "  status              Show status of all instances"
    echo "  logs [instance]     Tail log files"
    echo "  help                Show this help message"
    echo ""
    echo "Instances:"
    echo "  cloudflared   HTTP on 127.0.0.1:8000 (Cloudflare tunnel -> jonandem.com)"
    echo "  http          HTTP on 0.0.0.0:80 (direct LAN access)"
    echo "  https         HTTPS on 0.0.0.0:443 (NordVPN meshnet, self-signed cert)"
    echo "  all           All instances"
    echo ""
    echo "If instance is omitted:"
    echo "  start   -> starts all instances"
    echo "  stop    -> stops all running instances"
    echo "  restart -> restarts all running instances"
    echo "  logs    -> tails all log files"
    echo ""
    echo "Examples:"
    echo "  ./run_prod.sh start              # Start all instances"
    echo "  ./run_prod.sh restart cloudflared # Restart only the cloudflared instance"
    echo "  ./run_prod.sh status             # Show status of everything"
    echo "  ./run_prod.sh stop all           # Stop everything"
    echo ""
}

is_running() {
    local instance="$1"
    local pidfile="${PID_FILES[$instance]}"
    [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

# Get list of currently running instances
get_running_instances() {
    local running=()
    for inst in "${ALL_INSTANCES[@]}"; do
        if is_running "$inst"; then
            running+=("$inst")
        fi
    done
    echo "${running[@]}"
}

# Resolve which instances to operate on
resolve_instances() {
    local command="$1"
    local target="$2"

    if [ -n "$target" ] && [ "$target" != "all" ]; then
        # Validate instance name
        if [ -z "${PID_FILES[$target]+x}" ]; then
            echo -e "${RED}Unknown instance: $target${NC}" >&2
            echo "Valid instances: cloudflared, http, https, all" >&2
            exit 1
        fi
        echo "$target"
        return
    fi

    if [ "$target" = "all" ]; then
        echo "${ALL_INSTANCES[@]}"
        return
    fi

    # No target specified - behavior depends on command
    case "$command" in
        start|status)
            echo "${ALL_INSTANCES[@]}"
            ;;
        stop|restart)
            local running
            running=$(get_running_instances)
            if [ -z "$running" ]; then
                echo -e "${YELLOW}No instances currently running.${NC}" >&2
                if [ "$command" = "restart" ]; then
                    echo "${ALL_INSTANCES[@]}"
                fi
            else
                echo "$running"
            fi
            ;;
        logs)
            echo "${ALL_INSTANCES[@]}"
            ;;
    esac
}

find_env_file() {
    if [ -f ".env.prod" ]; then
        echo ".env.prod"
    elif [ -f ".env.prod.local" ]; then
        echo ".env.prod.local"
    else
        echo -e "${RED}Error: Neither .env.prod nor .env.prod.local found.${NC}" >&2
        exit 1
    fi
}

check_ssl_certs() {
    if [ -f "ssl/server.crt" ] && [ -f "ssl/server.key" ]; then
        return
    fi

    echo "SSL certificates not found. Generating..."
    mkdir -p ssl

    local external_ip meshnet_ip meshnet_hostname san
    external_ip=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google" 2>/dev/null || curl -s ifconfig.me 2>/dev/null || echo "localhost")
    meshnet_ip=$(ip addr show nord-tun 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "")
    meshnet_hostname=$(nordvpn meshnet peer list 2>/dev/null | grep "This device:" -A 1 | grep "Hostname:" | awk '{print $2}' || echo "")

    san="DNS:localhost,IP:127.0.0.1,IP:0.0.0.0,IP:$external_ip"
    [ -n "$meshnet_ip" ] && san="$san,IP:$meshnet_ip"
    [ -n "$meshnet_hostname" ] && san="$san,DNS:$meshnet_hostname"

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout ssl/server.key \
        -out ssl/server.crt \
        -subj "/C=US/ST=State/L=City/O=WineCellar/CN=$external_ip" \
        -addext "subjectAltName=$san"
    echo "SSL certificates generated."
}

# Run common setup tasks (migrations, superuser) once per invocation
SETUP_DONE=false
run_setup() {
    if [ "$SETUP_DONE" = true ]; then
        return
    fi

    if [ ! -d "venv" ]; then
        echo -e "${RED}Error: Virtual environment not found.${NC}"
        exit 1
    fi

    local env_file
    env_file=$(find_env_file)

    source venv/bin/activate
    set -a
    source "$env_file"
    set +a

    echo "Running migrations..."
    python manage.py migrate --no-input

    echo "Ensuring superuser exists..."
    python manage.py loaddata fixtures/grapes.json 2>/dev/null || true
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

    SETUP_DONE=true
}

# --- Core operations ---

start_instance() {
    local instance="$1"
    local pidfile="${PID_FILES[$instance]}"
    local logfile="${LOG_FILES[$instance]}"
    local bind="${BIND_ADDRS[$instance]}"
    local env_file
    env_file=$(find_env_file)

    if is_running "$instance"; then
        echo -e "  ${YELLOW}$instance${NC} already running (PID: $(cat "$pidfile"))"
        return
    fi

    # HTTPS needs SSL certs
    if [ "$instance" = "https" ]; then
        check_ssl_certs
    fi

    local ssl_args=""
    if [ "$instance" = "https" ]; then
        ssl_args="--certfile ssl/server.crt --keyfile ssl/server.key"
    fi

    nohup bash -c "
        source venv/bin/activate
        set -a
        source $env_file
        set +a
        exec venv/bin/gunicorn wine_cellar.conf.wsgi:application \
            --bind $bind \
            --worker-class sync \
            --workers 2 \
            --timeout 120 \
            $ssl_args \
            --pid '$pidfile'
    " >> "$logfile" 2>&1 &

    # Wait for gunicorn to create PID file
    for _ in {1..10}; do
        if is_running "$instance"; then
            break
        fi
        sleep 1
    done

    if is_running "$instance"; then
        echo -e "  ${GREEN}$instance${NC} started (PID: $(cat "$pidfile"), bind: $bind)"
    else
        echo -e "  ${RED}$instance${NC} failed to start. Check $logfile"
        return 1
    fi
}

stop_instance() {
    local instance="$1"
    local pidfile="${PID_FILES[$instance]}"

    if [ ! -f "$pidfile" ]; then
        echo -e "  ${YELLOW}$instance${NC} not running (no PID file)"
        return
    fi

    local pid
    pid=$(cat "$pidfile")

    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        # Wait for process to exit
        for _ in {1..10}; do
            if ! kill -0 "$pid" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        rm -f "$pidfile"
        echo -e "  ${GREEN}$instance${NC} stopped (was PID: $pid)"
    else
        rm -f "$pidfile"
        echo -e "  ${YELLOW}$instance${NC} not running (stale PID file removed)"
    fi
}

show_status() {
    echo ""
    echo "Wine Cellar - Production Server Status"
    echo "======================================="
    echo ""

    for instance in "${ALL_INSTANCES[@]}"; do
        local pidfile="${PID_FILES[$instance]}"
        local bind="${BIND_ADDRS[$instance]}"
        local logfile="${LOG_FILES[$instance]}"

        if is_running "$instance"; then
            local pid
            pid=$(cat "$pidfile")
            printf "  %-14s ${GREEN}running${NC}  PID: %-8s bind: %s\n" "$instance" "$pid" "$bind"
        else
            printf "  %-14s ${RED}stopped${NC}\n" "$instance"
        fi
    done

    # Cloudflared tunnel status
    echo ""
    if pgrep -f "cloudflared.*tunnel run" > /dev/null 2>&1; then
        echo -e "  cloudflare tunnel: ${GREEN}running${NC}"
    else
        echo -e "  cloudflare tunnel: ${RED}not running${NC}"
    fi

    echo ""
}

do_start() {
    local instances=($1)
    echo ""
    echo "Starting production server(s)..."
    echo ""
    run_setup
    echo ""
    local failed=0
    for instance in "${instances[@]}"; do
        start_instance "$instance" || failed=1
    done
    echo ""
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}Done.${NC}"
    else
        echo -e "${YELLOW}Some instances failed to start.${NC}"
    fi
}

do_stop() {
    local instances=($1)
    echo ""
    echo "Stopping production server(s)..."
    echo ""
    for instance in "${instances[@]}"; do
        stop_instance "$instance"
    done
    echo ""
    echo -e "${GREEN}Done.${NC}"
}

do_restart() {
    local instances=($1)
    echo ""
    echo "Restarting production server(s)..."
    echo ""

    # Stop
    for instance in "${instances[@]}"; do
        stop_instance "$instance"
    done

    sleep 2

    # Start (with shared setup)
    run_setup
    echo ""

    local failed=0
    for instance in "${instances[@]}"; do
        start_instance "$instance" || failed=1
    done
    echo ""
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}Done.${NC}"
    else
        echo -e "${YELLOW}Some instances failed to start.${NC}"
    fi
}

do_logs() {
    local instances=($1)
    local files=()
    for instance in "${instances[@]}"; do
        local logfile="${LOG_FILES[$instance]}"
        if [ -f "$logfile" ]; then
            files+=("$logfile")
        fi
    done

    if [ ${#files[@]} -eq 0 ]; then
        echo "No log files found."
        exit 0
    fi

    echo "Tailing: ${files[*]}"
    tail -f "${files[@]}"
}

# --- Main ---

COMMAND="${1:-help}"
INSTANCE="${2:-}"

case "$COMMAND" in
    start)
        instances=$(resolve_instances start "$INSTANCE")
        [ -n "$instances" ] && do_start "$instances"
        ;;
    stop)
        instances=$(resolve_instances stop "$INSTANCE")
        [ -n "$instances" ] && do_stop "$instances"
        ;;
    restart)
        instances=$(resolve_instances restart "$INSTANCE")
        [ -n "$instances" ] && do_restart "$instances"
        ;;
    status)
        show_status
        ;;
    logs)
        instances=$(resolve_instances logs "$INSTANCE")
        [ -n "$instances" ] && do_logs "$instances"
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
