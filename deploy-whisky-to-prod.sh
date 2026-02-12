#!/bin/bash
# Whisky Cellar - Production Deployment Script (Docker)
#
# Rebuilds and restarts the whisky-web container in the shared Docker stack.
#
# Usage:
#   ./deploy-whisky-to-prod.sh              # Full deployment
#   ./deploy-whisky-to-prod.sh --skip-tests # Skip tests (for hotfixes)
#   ./deploy-whisky-to-prod.sh --build-only # Only build, don't restart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Options
SKIP_TESTS=false
BUILD_ONLY=false

# Parse arguments
for arg in "$@"; do
    case $arg in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --help|-h)
            echo "Whisky Cellar - Production Deployment Script (Docker)"
            echo ""
            echo "Usage: ./deploy-whisky-to-prod.sh [options]"
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
echo "  Whisky Cellar - Docker Deployment"
echo "=========================================="
echo ""

# Step 1: Run tests (unless skipped)
if [ "$SKIP_TESTS" = false ]; then
    log "Step 1/4: Running tests..."
    if [ -d "venv" ]; then
        if ! CELLAR_APP_TYPE=whisky venv/bin/py.test tests/whisky/ --reuse-db -q; then
            error "Whisky tests failed. Fix test failures before deploying."
        fi
        success "Tests passed"
    else
        warn "No venv found, skipping local tests"
    fi
else
    warn "Step 1/4: Skipping tests (--skip-tests flag)"
fi

# Step 2: Build frontend assets
log "Step 2/4: Building frontend assets..."
if [ -d "node_modules" ]; then
    if ! npm run build:prod; then
        error "Frontend build failed."
    fi
    success "Frontend build complete"
else
    warn "No node_modules found, skipping frontend build"
fi

# Step 3: Rebuild Docker image
log "Step 3/4: Rebuilding Docker image..."
if ! docker compose -f docker-compose.prod.yml build wine-web; then
    error "Docker image build failed."
fi
success "Docker image rebuilt"

# Step 4: Restart whisky-web container (unless build-only)
if [ "$BUILD_ONLY" = false ]; then
    log "Step 4/4: Restarting whisky-web container..."
    docker compose -f docker-compose.prod.yml up -d whisky-web
    success "Whisky container restarted"
else
    warn "Step 4/4: Skipping restart (--build-only flag)"
fi

echo ""
echo "=========================================="
echo -e "  ${GREEN}Whisky deployment complete!${NC}"
echo "=========================================="
echo ""
