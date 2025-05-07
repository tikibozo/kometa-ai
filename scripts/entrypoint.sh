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

# Switch to kometa user and run the command
exec gosu kometa "$@"