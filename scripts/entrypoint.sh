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

# Make sure the app directories have the right permissions. /app itself must
# be writable so the claude CLI (CLAUDE_BACKEND=cli) can create ~/.claude.json
chown kometa:kometa /app
chown -R kometa:kometa /app/kometa-config /app/state /app/logs

# Claude CLI credentials mount (CLAUDE_BACKEND=cli)
if [ -d /app/.claude ]; then
    chown -R kometa:kometa /app/.claude
fi

# CLAUDE_BACKEND=cli: fetch the Claude Code CLI on first start so the
# published image stays small. Survives restarts; re-downloads only when
# the container is recreated.
if [ "${CLAUDE_BACKEND:-api}" = "cli" ] && ! command -v claude >/dev/null 2>&1; then
    echo "CLAUDE_BACKEND=cli: installing Claude Code CLI..."
    if HOME=/app bash -c "curl -fsSL https://claude.ai/install.sh | bash"; then
        ln -sf /app/.local/bin/claude /usr/local/bin/claude
        chown -R kometa:kometa /app/.local
        echo "Claude CLI installed: $(claude --version 2>/dev/null || echo '(version check failed)')"
    else
        echo "ERROR: Claude CLI install failed; CLAUDE_BACKEND=cli will not work" >&2
    fi
fi

# Switch to kometa user and run the command. gosu preserves the environment,
# so set HOME explicitly — the claude CLI (CLAUDE_BACKEND=cli) resolves its
# credentials from $HOME/.claude
export HOME=/app
exec gosu kometa "$@"