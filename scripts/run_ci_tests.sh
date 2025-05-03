#!/bin/bash
# Script to run CI-compatible tests

set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Install dependencies if requested
if [ "$1" = "--install" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -r requirements-dev.txt
    pip install -e .
    shift
fi

# Set CI mode to skip production deployment tests
export CI=true
export SKIP_PRODUCTION_TESTS=true

# Install package in development mode
echo "Installing package in development mode..."
pip install -e .

# Run tests with coverage
echo "Running tests..."
pytest -xvs $@

# Generate coverage report
echo "Generating coverage report..."
coverage xml
coverage html

echo "Tests completed successfully!"