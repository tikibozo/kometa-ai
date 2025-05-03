#!/bin/bash
# Script to set up the package structure before building the package
# This ensures all the necessary py.typed files exist and directories are created

set -e

echo "Running pre-build setup..."

# Create required directories
mkdir -p kometa_ai/state kometa_ai/claude kometa_ai/common kometa_ai/kometa
mkdir -p kometa_ai/notification kometa_ai/radarr kometa_ai/utils

# Create empty py.typed files in each directory
touch kometa_ai/py.typed
touch kometa_ai/state/py.typed
touch kometa_ai/claude/py.typed
touch kometa_ai/common/py.typed
touch kometa_ai/kometa/py.typed
touch kometa_ai/notification/py.typed
touch kometa_ai/radarr/py.typed
touch kometa_ai/utils/py.typed

# Verify files exist
echo "Verifying py.typed files:"
find kometa_ai -name py.typed

echo "Pre-build setup complete!"