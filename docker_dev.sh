#!/bin/bash
# Script to build and run the Docker development environment

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker daemon is not running"
    exit 1
fi

# Build the development image
echo "Building development Docker image..."
docker build -f Dockerfile.dev -t kometa-ai-dev .

# Check if the build was successful
if [ $? -ne 0 ]; then
    echo "Error: Docker build failed"
    exit 1
fi

# Set up environment for development
mkdir -p logs state test_data/kometa-config
cp -n test_data/kometa-config/collections.yml test_data/kometa-config/ 2>/dev/null || true

# Run the development container
echo "Starting development container..."
docker run --rm -it \
    -v "$(pwd):/app" \
    -v "$(pwd)/test_data/kometa-config:/app/kometa-config" \
    -v "$(pwd)/state:/app/state" \
    -v "$(pwd)/logs:/app/logs" \
    -e RADARR_URL="http://localhost:7878" \
    -e RADARR_API_KEY="dev_api_key" \
    -e CLAUDE_API_KEY="dev_api_key" \
    -e DEBUG_LOGGING="true" \
    kometa-ai-dev --run-now --dry-run