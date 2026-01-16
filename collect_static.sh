#!/bin/bash
# Wine Cellar - Static Files Collection Script
#
# Collects and compresses static files for production deployment.
# Can be run manually or via cron for regular updates.
#
# Usage: ./collect_static.sh [--quiet] [--force]
#
# Options:
#   --quiet, -q   Suppress output (for cron)
#   --force, -f   Force rebuild even if staticfiles exist
#
# Cron example (run daily at 3am):
#   0 3 * * * /home/jonhall145/wine/collect_static.sh --quiet >> /home/jonhall145/wine/logs/collectstatic.log 2>&1

set -e

# Script directory (for running from cron)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

QUIET=false
FORCE=false
LOG_FILE="logs/collectstatic.log"

# Parse arguments
for arg in "$@"; do
    case $arg in
        --quiet|-q)
            QUIET=true
            shift
            ;;
        --force|-f)
            FORCE=true
            shift
            ;;
    esac
done

# Logging function
log() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    log "ERROR: Virtual environment not found at $SCRIPT_DIR/venv"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Load production environment if available, fall back to dev
if [ -f ".env.prod.local" ]; then
    set -a
    source .env.prod.local
    set +a
elif [ -f ".env.dev" ]; then
    set -a
    source .env.dev
    set +a
fi

# Ensure logs directory exists
mkdir -p logs

# Check if we can skip (manifest exists and not forcing)
MANIFEST_FILE="staticfiles/staticfiles.json"
if [ -f "$MANIFEST_FILE" ] && [ "$FORCE" = false ]; then
    log "Staticfiles manifest exists. Use --force to rebuild."
    log "Skipping collectstatic (already built)."
    deactivate 2>/dev/null || true
    exit 0
fi

log "Starting static file collection..."

# Run collectstatic (gzip-only compression via custom storage backend)
if [ "$QUIET" = true ]; then
    python manage.py collectstatic --noinput --verbosity 0
else
    python manage.py collectstatic --noinput
fi

# Get count of static files
STATIC_COUNT=$(find staticfiles -type f 2>/dev/null | wc -l)

log "Static file collection complete. Total files: $STATIC_COUNT"

# Deactivate virtual environment
deactivate 2>/dev/null || true
