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

# Set Python path to include the current directory
export PYTHONPATH="$PYTHONPATH:$(pwd)"
echo "PYTHONPATH set to: $PYTHONPATH"

# Create a symlink in tests directory to ensure kometa_ai can be imported
echo "Setting up test environment..."

# Install package in development mode
echo "Installing package in development mode..."
python -m pip install -e . --verbose

# Create a simple helper script to ensure imports work
cat > import_helper.py << EOF
import sys
import os

# Add the current directory to sys.path
sys.path.insert(0, os.getcwd())

# Import the problematic modules to verify they can be found
try:
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    print("Successfully imported state modules!")
except ImportError as e:
    print(f"Failed to import: {e}")
    sys.exit(1)
EOF

# Execute the helper script to verify imports
echo "Testing imports..."
python import_helper.py

# Run tests with coverage
echo "Running tests..."
PYTHONPATH=. pytest -xvs $@

# Generate coverage report
echo "Generating coverage report..."
coverage xml
coverage html

echo "Tests completed successfully!"