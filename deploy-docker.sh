#!/bin/bash
# Production Deployment Script (Docker)
#
# Rebuilds and restarts the app container in the shared Docker stack.
#
# Usage:
#   ./deploy-docker.sh wine                # Deploy wine app
#   ./deploy-docker.sh whisky              # Deploy whisky app
#   ./deploy-docker.sh whisky --skip-tests # Skip tests (for hotfixes)
#   ./deploy-docker.sh wine --build-only   # Only build, don't restart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# App type (first argument)
APP_TYPE="${1:-}"
shift 2>/dev/null || true

if [ "$APP_TYPE" != "wine" ] && [ "$APP_TYPE" != "whisky" ]; then
    echo "Usage: ./deploy-docker.sh <wine|whisky> [options]"
    echo ""
    echo "Options:"
    echo "  --skip-tests    Skip running tests (for hotfixes)"
    echo "  --build-only    Only build image, don't restart container"
    echo "  --help, -h      Show this help message"
    exit 1
fi

APP_LABEL="$(echo "$APP_TYPE" | sed 's/./\U&/')"
CONTAINER="${APP_TYPE}-web"

# Options
SKIP_TESTS=false
BUILD_ONLY=false

for arg in "$@"; do
    case $arg in
        --skip-tests)
            SKIP_TESTS=true
            ;;
        --build-only)
            BUILD_ONLY=true
            ;;
        --help|-h)
            echo "${APP_LABEL} Cellar - Production Deployment Script (Docker)"
            echo ""
            echo "Usage: ./deploy-docker.sh ${APP_TYPE} [options]"
            echo ""
            echo "Options:"
            echo "  --skip-tests    Skip running tests (for hotfixes)"
            echo "  --build-only    Only build image, don't restart container"
            echo "  --help, -h      Show this help message"
            exit 0
            ;;
    esac
done

log() {
    echo -e "${BLUE}[DEPLOY]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

echo ""
echo "=========================================="
echo "  ${APP_LABEL} Cellar - Docker Deployment"
echo "=========================================="
echo ""

# Step 1: Run tests (unless skipped)
if [ "$SKIP_TESTS" = false ]; then
    log "Step 1/5: Running tests..."
    if [ -d "venv" ]; then
        if [ "$APP_TYPE" = "whisky" ]; then
            if ! CELLAR_APP_TYPE=whisky venv/bin/py.test tests/whisky/ --reuse-db -q; then
                error "Whisky tests failed. Fix test failures before deploying."
            fi
        else
            if ! venv/bin/py.test tests/ --reuse-db -q --ignore=tests/whisky/; then
                error "Wine tests failed. Fix test failures before deploying."
            fi
        fi
        success "Tests passed"
    else
        warn "No venv found, skipping local tests"
    fi
else
    warn "Step 1/5: Skipping tests (--skip-tests flag)"
fi

# Step 2: Build frontend assets
log "Step 2/5: Building frontend assets..."
if [ -d "node_modules" ]; then
    if ! npm run build:prod; then
        error "Frontend build failed."
    fi
    success "Frontend build complete"
else
    warn "No node_modules found, skipping frontend build"
fi

# Step 3: Collect static files
log "Step 3/5: Collecting static files..."
if [ -d "venv" ]; then
    CELLAR_APP_TYPE="$APP_TYPE" venv/bin/python3 manage.py collectstatic --noinput
    success "Static files collected"
else
    warn "No venv found, skipping collectstatic (will run in Docker entrypoint)"
fi

# Step 4: Rebuild Docker image
log "Step 4/5: Rebuilding Docker image..."
if ! docker compose -f docker-compose.prod.yml build wine-web; then
    error "Docker image build failed."
fi
success "Docker image rebuilt"

# Step 5: Restart container (unless build-only)
if [ "$BUILD_ONLY" = false ]; then
    log "Step 5/5: Restarting ${CONTAINER} container..."
    docker compose -f docker-compose.prod.yml up -d "$CONTAINER"
    success "${APP_LABEL} container restarted"
else
    warn "Step 5/5: Skipping restart (--build-only flag)"
fi

echo ""
echo "=========================================="
echo -e "  ${GREEN}${APP_LABEL} deployment complete!${NC}"
echo "=========================================="
echo ""
