#!/usr/bin/env bash
# Build the frontend and place output in pipeline_web/dist/
# Run once before starting server.py, or after UI changes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/web"

echo "Installing dependencies..."
npm install

echo "Building..."
npm run build

echo "Done. Output: $SCRIPT_DIR/pipeline_web/dist/"
