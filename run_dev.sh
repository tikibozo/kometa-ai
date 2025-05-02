#!/bin/bash
# Development script to run Kometa-AI with mock data

# Set environment variables for development
export RADARR_URL="http://localhost:7878"
export RADARR_API_KEY="dev_api_key"
export CLAUDE_API_KEY="dev_api_key"
export DEBUG_LOGGING="true"

# Create necessary directories if they don't exist
mkdir -p logs state

# Run the application
python -m kometa_ai --run-now --dry-run $@