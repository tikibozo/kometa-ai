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

# Create a script to fix the state directory issue
cat > fix_state_dir.py << EOF
import os
import sys
import shutil
from pathlib import Path

# Get the site-packages directory
import site
site_packages = site.getsitepackages()[0]
print(f"Site packages dir: {site_packages}")

# Create the kometa_ai/state directory if it doesn't exist
kometa_state_dir = os.path.join(site_packages, "kometa_ai", "state")
os.makedirs(kometa_state_dir, exist_ok=True)
print(f"Created/ensured {kometa_state_dir} exists")

# Check the source directory
src_state_dir = os.path.join(os.getcwd(), "kometa_ai", "state")
print(f"Source state dir: {src_state_dir}")

# Copy the state files to the site-packages directory
for filename in ["__init__.py", "manager.py", "models.py"]:
    src_file = os.path.join(src_state_dir, filename)
    dst_file = os.path.join(kometa_state_dir, filename)
    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {src_file} to {dst_file}")
    else:
        print(f"Warning: Source file {src_file} not found")

# List the contents of the directory
print("Contents of state directory in site-packages:")
for item in os.listdir(kometa_state_dir):
    print(f"  {item}")

# Try importing the modules
try:
    sys.path.insert(0, site_packages)
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    print("Successfully imported state modules!")
except ImportError as e:
    print(f"Warning: Import still failed: {e}")
    # Don't exit with an error, we'll use mocks if needed
EOF

# Execute the helper script to fix the state directory
echo "Fixing state directory..."
python fix_state_dir.py

# Run tests with coverage
echo "Running tests..."
PYTHONPATH=. pytest -xvs $@

# Generate coverage report
echo "Generating coverage report..."
coverage xml
coverage html

echo "Tests completed successfully!"