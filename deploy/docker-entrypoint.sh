#!/bin/sh
# NexAlfa Docker Entrypoint
# Copies default workspace files into the mounted volume on first boot.
# User edits persist across redeploys because we only copy if the file is missing.

DEFAULTS_DIR="/app/workspace-defaults"
WORKSPACE_DIR="/app/workspace"

echo "🚀 NexAlfa: Initializing workspace..."

# Copy default files only if they don't already exist
for file in SOUL.md AGENTS.md USER.md MEMORY.md; do
    if [ -f "$DEFAULTS_DIR/$file" ] && [ ! -f "$WORKSPACE_DIR/$file" ]; then
        cp "$DEFAULTS_DIR/$file" "$WORKSPACE_DIR/$file"
        echo "  ✅ Copied default $file"
    fi
done

# Create skills directory if it doesn't exist
mkdir -p "$WORKSPACE_DIR/skills"
mkdir -p "$WORKSPACE_DIR/personalities"

echo "🚀 NexAlfa: Workspace ready. Starting gateway..."

# Execute the original CMD
exec "$@"
