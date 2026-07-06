#!/bin/bash
set -e

# Default PUID/PGID to 1000 if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "
-------------------------------------
Kometa-AI Container
-------------------------------------
User UID:    $PUID
User GID:    $PGID
-------------------------------------
"

# Change kometa user's UID and GID to match the provided values
groupmod -o -g "$PGID" kometa
usermod -o -u "$PUID" kometa

# Make sure the app directories have the right permissions
chown -R kometa:kometa /app/kometa-config /app/state /app/logs

# Claude CLI credentials mount (CLAUDE_BACKEND=cli)
if [ -d /app/.claude ]; then
    chown -R kometa:kometa /app/.claude
fi

# Switch to kometa user and run the command. gosu preserves the environment,
# so set HOME explicitly — the claude CLI (CLAUDE_BACKEND=cli) resolves its
# credentials from $HOME/.claude
export HOME=/app
exec gosu kometa "$@"