#!/bin/bash
# Smoke test script - checks all key pages for 500 errors
# Usage: ./scripts/smoke_test.sh [base_url]
# Example: ./scripts/smoke_test.sh http://localhost:8003

set -e

BASE_URL="${1:-http://localhost:8003}"
COOKIE_FILE="/tmp/smoke_test_cookies.txt"
FAILED=0
PASSED=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Wine Cellar Smoke Test ==="
echo "Base URL: $BASE_URL"
echo ""

# Clean up old cookies
rm -f "$COOKIE_FILE"

# Function to test a URL
test_url() {
    local url="$1"
    local name="$2"
    local expected_code="${3:-200}"

    # Make request and capture status code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_FILE" -c "$COOKIE_FILE" -L "$BASE_URL$url")

    if [ "$status_code" == "500" ]; then
        echo -e "${RED}✗ FAIL${NC} [$status_code] $name ($url)"
        FAILED=$((FAILED + 1))
        return 1
    elif [ "$status_code" == "$expected_code" ] || [ "$status_code" == "200" ]; then
        echo -e "${GREEN}✓ PASS${NC} [$status_code] $name"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${YELLOW}? WARN${NC} [$status_code] $name ($url) - expected $expected_code"
        PASSED=$((PASSED + 1))
        return 0
    fi
}

# Function to login
do_login() {
    echo "Logging in as testuser..."

    # Get CSRF token from login page
    csrf_token=$(curl -s -c "$COOKIE_FILE" "$BASE_URL/accounts/login/" | grep -oP 'name="csrfmiddlewaretoken" value="\K[^"]+' | head -1)

    if [ -z "$csrf_token" ]; then
        echo -e "${RED}Failed to get CSRF token${NC}"
        exit 1
    fi

    # Login
    login_result=$(curl -s -o /dev/null -w "%{http_code}" \
        -b "$COOKIE_FILE" -c "$COOKIE_FILE" \
        -X POST "$BASE_URL/accounts/login/" \
        -H "Referer: $BASE_URL/accounts/login/" \
        -d "csrfmiddlewaretoken=$csrf_token&login=testuser&password=testpass123")

    if [ "$login_result" == "302" ] || [ "$login_result" == "200" ]; then
        echo -e "${GREEN}Login successful${NC}"
        echo ""
    else
        echo -e "${RED}Login failed with status $login_result${NC}"
        exit 1
    fi
}

# Check if server is running
echo "Checking if server is running..."
if ! curl -s -o /dev/null "$BASE_URL/health/"; then
    echo -e "${RED}Server not responding at $BASE_URL${NC}"
    echo "Start the server with: make server"
    exit 1
fi
echo -e "${GREEN}Server is running${NC}"
echo ""

# Login first
do_login

echo "=== Testing Pages ==="
echo ""

# Public pages
echo "--- Public Pages ---"
test_url "/health/" "Health check"

# Main pages
echo ""
echo "--- Main Pages ---"
test_url "/" "Homepage"
test_url "/wines/" "Wine list"
test_url "/wines/map/" "Wine map"
test_url "/bottles/" "Bottle list"
test_url "/storages/" "Storage list"
test_url "/drink-history/" "Drink history"
test_url "/wishlist/" "Wishlist"
test_url "/cellar-value/" "Cellar value"
test_url "/alerts/" "Drinking window alerts"
test_url "/stats/" "Consumption stats"
test_url "/reorder/" "Reorder reminders"
test_url "/sale-alerts/" "Sale alerts"
test_url "/user/settings/" "User settings"

# Create/Add pages
echo ""
echo "--- Create Pages ---"
test_url "/wine/add/" "Add wine"
test_url "/wine/scan/" "Scan wine"
test_url "/storage/add/" "Add storage"
test_url "/wishlist/add/" "Add wishlist item"
test_url "/sale-alerts/add/" "Add sale alert"
test_url "/label-scan/" "Label scan"

# Get IDs for detail/edit pages
echo ""
echo "--- Getting test data IDs ---"

# Get a wine ID
WINE_ID=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/wines/" | grep -oP 'href="/wine/\K\d+' | head -1)
if [ -n "$WINE_ID" ]; then
    echo "Found wine ID: $WINE_ID"
else
    echo -e "${YELLOW}No wines found, skipping wine detail tests${NC}"
fi

# Get a storage ID
STORAGE_ID=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/storages/" | grep -oP 'href="/storage/\K\d+' | head -1)
if [ -n "$STORAGE_ID" ]; then
    echo "Found storage ID: $STORAGE_ID"
else
    echo -e "${YELLOW}No storages found, skipping storage detail tests${NC}"
fi

# Get a bottle ID
BOTTLE_ID=$(curl -s -b "$COOKIE_FILE" "$BASE_URL/bottles/" | grep -oP 'href="/bottle/edit/\K\d+' | head -1)
if [ -n "$BOTTLE_ID" ]; then
    echo "Found bottle ID: $BOTTLE_ID"
else
    echo -e "${YELLOW}No bottles found, skipping bottle edit tests${NC}"
fi

# Detail/Edit pages
echo ""
echo "--- Detail/Edit Pages ---"

if [ -n "$WINE_ID" ]; then
    test_url "/wine/$WINE_ID/" "Wine detail"
    test_url "/wine/edit/$WINE_ID/" "Wine edit"
    test_url "/wine/$WINE_ID/drink/" "Drink record"
    test_url "/stock/add/$WINE_ID/" "Add stock"
fi

if [ -n "$STORAGE_ID" ]; then
    test_url "/storage/$STORAGE_ID/" "Storage detail"
    test_url "/storage/edit/$STORAGE_ID/" "Storage edit"
fi

if [ -n "$BOTTLE_ID" ]; then
    test_url "/bottle/edit/$BOTTLE_ID/" "Bottle edit"
    test_url "/bottle/$BOTTLE_ID/note/" "Bottle note"
fi

# Storage history
test_url "/storage/history/" "Storage history"

# Summary
echo ""
echo "=== Summary ==="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"

# Cleanup
rm -f "$COOKIE_FILE"

if [ $FAILED -gt 0 ]; then
    echo ""
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
