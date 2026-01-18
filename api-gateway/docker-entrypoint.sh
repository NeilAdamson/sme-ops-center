#!/bin/sh
set -e

# Fix permissions for uploads and sessions directories if they exist
# This runs as root before switching to user 1000
if [ -d "/app/uploads" ]; then
    chown -R 1000:1000 /app/uploads || true
    chmod -R 755 /app/uploads || true
fi

if [ -d "/app/sessions" ]; then
    chown -R 1000:1000 /app/sessions || true
    chmod -R 755 /app/sessions || true
fi

# Switch to non-root user and execute command
if [ "$(id -u)" = "0" ]; then
    # If running as root, switch to user fastapi (UID 1000) using runuser
    # First check if user exists, create if not
    if ! id -u 1000 > /dev/null 2>&1; then
        useradd -m -u 1000 fastapi || true
    fi
    exec runuser -u fastapi -- "$@"
else
    # If already running as non-root, just execute
    exec "$@"
fi
