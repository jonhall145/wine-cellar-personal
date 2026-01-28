#!/bin/bash
# Wine Cellar - Production Deployment Script
#
# Pushes code changes through to production by running tests, building
# frontend assets, collecting static files, and restarting the server.
#
# Usage:
#   ./deploy-to-prod.sh              # Full deployment
#   ./deploy-to-prod.sh --skip-tests # Skip tests (for hotfixes)
#   ./deploy-to-prod.sh --build-only # Only build, don't restart server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
            echo "Wine Cellar - Production Deployment Script"
            echo ""
            echo "Usage: ./deploy-to-prod.sh [options]"
            echo ""
            echo "Options:"
            echo "  --skip-tests    Skip running tests (for hotfixes)"
            echo "  --build-only    Only build assets, don't restart server"
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
echo "  Wine Cellar - Production Deployment"
echo "=========================================="
echo ""

# Check prerequisites
if [ ! -d "venv" ]; then
    error "Virtual environment not found. Run 'make install' first."
fi

if [ ! -d "node_modules" ]; then
    error "Node modules not found. Run 'npm install' first."
fi

# Activate virtual environment
source venv/bin/activate

# Step 1: Run tests (unless skipped)
if [ "$SKIP_TESTS" = false ]; then
    log "Step 1/5: Running tests..."
    if ! venv/bin/py.test --reuse-db -q; then
        error "Tests failed. Fix test failures before deploying."
    fi
    success "Tests passed"
else
    warn "Step 1/5: Skipping tests (--skip-tests flag)"
fi

# Step 2: Run linting
log "Step 2/5: Running linting checks..."
LINT_EXIT=0

# Python linting
venv/bin/isort --diff -c wine_cellar tests 2>/dev/null || LINT_EXIT=1
venv/bin/flake8 wine_cellar tests --exclude migrations,settings 2>/dev/null || LINT_EXIT=1

# JS linting
npm run lint 2>/dev/null || LINT_EXIT=1

# Check for missing migrations
venv/bin/python manage.py makemigrations --dry-run --check --noinput 2>/dev/null || LINT_EXIT=1

if [ $LINT_EXIT -ne 0 ]; then
    warn "Linting issues found. Consider fixing before deploying."
else
    success "Linting passed"
fi

# Step 3: Build frontend assets (LONG RUNNING)
log "Step 3/5: Building frontend assets (this may take a while)..."
echo "    Running: npm run build:prod"
if ! npm run build:prod; then
    error "Frontend build failed."
fi
success "Frontend build complete"

# Step 4: Collect static files (LONG RUNNING)
log "Step 4/5: Collecting static files (this may take a while)..."
echo "    Running: ./collect_static.sh --force"
if ! ./collect_static.sh --force; then
    error "Static file collection failed."
fi
success "Static files collected"

# Step 5: Restart production server (unless build-only)
if [ "$BUILD_ONLY" = false ]; then
    log "Step 5/5: Starting/restarting production server..."

    # Check if production server is running
    if [ -f "/tmp/wine_cellar_gunicorn_https.pid" ] && kill -0 $(cat /tmp/wine_cellar_gunicorn_https.pid) 2>/dev/null; then
        echo "    Restarting HTTPS server..."
        sudo ./run_prod_https.sh restart
        success "HTTPS server restarted"
    elif [ -f "/tmp/wine_cellar_gunicorn.pid" ] && kill -0 $(cat /tmp/wine_cellar_gunicorn.pid) 2>/dev/null; then
        echo "    Restarting HTTP server..."
        ./run_prod_local.sh restart
        success "HTTP server restarted"
    else
        echo "    No server running. Starting HTTPS server..."
        sudo ./run_prod_https.sh start
        success "HTTPS server started"
    fi
else
    warn "Step 5/5: Skipping server restart (--build-only flag)"
fi

echo ""
echo "=========================================="
echo -e "  ${GREEN}Deployment complete!${NC}"
echo "=========================================="
echo ""
