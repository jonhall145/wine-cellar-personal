#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code web environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

echo "=== Setting up wine-cellar-personal environment ==="

# Create Python virtual environment if it doesn't exist (using Python 3.12)
if [ ! -d venv ]; then
  echo "Creating Python virtual environment..."
  python3.12 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies (base + dev tools for linting and testing)
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install npm dependencies
echo "Installing npm dependencies..."
npm install --no-save

# Build frontend
echo "Building frontend..."
npm run build

# Run Django migrations
echo "Running Django migrations..."
python manage.py migrate

echo "=== Environment setup complete ==="
