#!/bin/bash
# Script to run Kometa-AI locally with virtual environment

# Source the virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.initialized" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    pip install -e .  # Install the package in development mode
    touch venv/.initialized
fi

# Set environment variables
export RADARR_URL="http://localhost:7878"
export RADARR_API_KEY="dev_api_key"
export CLAUDE_API_KEY="dev_api_key"
export DEBUG_LOGGING="true"

# Create necessary directories
mkdir -p logs state kometa-config
cp -n test_data/kometa-config/collections.yml kometa-config/ 2>/dev/null || true

# Run the application
python -m kometa_ai "$@"

# Deactivate the virtual environment
deactivate