#!/bin/bash
set -euo pipefail

echo "Syncing with GitHub..." >&2
git -C "$CLAUDE_PROJECT_DIR" pull origin main --ff-only 2>&1 || {
    echo "Warning: git pull failed (offline or merge conflict). Continuing with local files." >&2
}
