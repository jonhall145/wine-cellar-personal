#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code web environment
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

if [ -z "${CLAUDE_PROJECT_DIR:-}" ]; then
  echo "Error: CLAUDE_PROJECT_DIR is not set; cannot initialize environment." >&2
  exit 1
fi
cd "$CLAUDE_PROJECT_DIR"

echo "=== Setting up wine-cellar-personal environment ==="

# Delegate full environment setup to Makefile to avoid drift
make install
echo "=== Environment setup complete ==="
