#!/bin/bash
# Script to run tests in a virtual environment

# Options
INCLUDE_PRODUCTION=false
FORCE_INSTALL=false

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --force-install)
            FORCE_INSTALL=true
            shift
            ;;
        --include-production)
            INCLUDE_PRODUCTION=true
            shift
            ;;
        *)
            # Save remaining arguments for pytest
            PYTEST_ARGS+=("$1")
            shift
            ;;
    esac
done

# Source the virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.initialized" ] || [ "$FORCE_INSTALL" == "true" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install -e .
    touch venv/.initialized
fi

# Set environment variables for production test skipping
if [ "$INCLUDE_PRODUCTION" == "false" ]; then
    export SKIP_PRODUCTION_TESTS=true
    echo "Skipping production deployment tests (use --include-production to include them)"
else
    unset SKIP_PRODUCTION_TESTS
    echo "Including production deployment tests"
fi

# Run the tests
if [ ${#PYTEST_ARGS[@]} -eq 0 ]; then
    echo "Running all tests..."
    pytest tests/
else
    echo "Running specified tests: ${PYTEST_ARGS[@]}"
    pytest "${PYTEST_ARGS[@]}"
fi

# Deactivate the virtual environment
deactivate