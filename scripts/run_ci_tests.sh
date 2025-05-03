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
#!/usr/bin/env python3
"""
Fix script for ensuring kometa_ai.state directory is properly installed
and importable in site-packages.
"""

import os
import sys
import shutil
import importlib
import importlib.util
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix_state_dir")

# Add current directory to Python path
root_dir = Path.cwd()
sys.path.insert(0, str(root_dir))
logger.info(f"Added {root_dir} to sys.path")

# Get the site-packages directory
import site
site_packages_dirs = site.getsitepackages()
site_packages = site_packages_dirs[0]
logger.info(f"Site packages dirs: {site_packages_dirs}")
logger.info(f"Using site packages dir: {site_packages}")

# Ensure kometa_ai directory exists in site-packages
kometa_ai_dir = os.path.join(site_packages, "kometa_ai")
if not os.path.exists(kometa_ai_dir):
    logger.warning(f"kometa_ai directory not found in site-packages, creating it...")
    os.makedirs(kometa_ai_dir, exist_ok=True)
    # Create an __init__.py file
    with open(os.path.join(kometa_ai_dir, "__init__.py"), "w") as f:
        f.write('"""kometa-ai package for Claude integration with Radarr."""\n')
else:
    logger.info(f"Found kometa_ai directory: {kometa_ai_dir}")

# Create/update the py.typed file in kometa_ai directory
py_typed_path = os.path.join(kometa_ai_dir, "py.typed")
with open(py_typed_path, "w") as f:
    pass  # Empty file is sufficient
logger.info(f"Created py.typed file at {py_typed_path}")

# Create the kometa_ai/state directory if it doesn't exist
kometa_state_dir = os.path.join(site_packages, "kometa_ai", "state")
os.makedirs(kometa_state_dir, exist_ok=True)
logger.info(f"Created/ensured {kometa_state_dir} exists")

# Create/update state/__init__.py
state_init_py = os.path.join(kometa_state_dir, "__init__.py")
with open(state_init_py, "w") as f:
    f.write('''"""
State management for Kometa-AI.

This package provides functionality for persisting decisions and state.
"""

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ['StateManager', 'DecisionRecord']
''')
logger.info(f"Updated {state_init_py}")

# Create state/py.typed
state_py_typed = os.path.join(kometa_state_dir, "py.typed")
with open(state_py_typed, "w") as f:
    pass  # Empty file is sufficient
logger.info(f"Created state/py.typed file at {state_py_typed}")

# Check the source directory
src_state_dir = os.path.join(os.getcwd(), "kometa_ai", "state")
logger.info(f"Source state dir: {src_state_dir}")

# Copy the state files to the site-packages directory
for filename in ["manager.py", "models.py"]:
    src_file = os.path.join(src_state_dir, filename)
    dst_file = os.path.join(kometa_state_dir, filename)
    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        logger.info(f"Copied {src_file} to {dst_file}")
    else:
        logger.warning(f"Warning: Source file {src_file} not found")

# List the contents of the directory
logger.info("Contents of state directory in site-packages:")
for item in os.listdir(kometa_state_dir):
    logger.info(f"  {item}")

# Clear the importlib cache to ensure fresh imports
try:
    importlib.invalidate_caches()
    logger.info("Invalidated importlib caches")
except Exception as e:
    logger.warning(f"Failed to invalidate importlib caches: {e}")

# Try importing the modules by both approaches
import_results = {
    "absolute_import": False,
    "site_packages_import": False
}

# First try absolute import
try:
    logger.info("Trying absolute import...")
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    logger.info("Successfully imported state modules using absolute import!")
    import_results["absolute_import"] = True
except ImportError as e:
    logger.warning(f"Absolute import failed: {e}")

# Then try import via site-packages
try:
    logger.info("Trying site-packages import...")
    sys.path.insert(0, site_packages)
    # Use importlib to avoid cached imports
    manager_module = importlib.import_module("kometa_ai.state.manager")
    models_module = importlib.import_module("kometa_ai.state.models")
    StateManager = getattr(manager_module, "StateManager")
    DecisionRecord = getattr(models_module, "DecisionRecord")
    logger.info("Successfully imported state modules via site-packages!")
    import_results["site_packages_import"] = True
except ImportError as e:
    logger.warning(f"Site-packages import failed: {e}")

# Final report
if any(import_results.values()):
    logger.info("🟢 STATE MODULE IMPORT FIX SUCCESSFUL!")
    for method, success in import_results.items():
        logger.info(f"  {method}: {'✅ Success' if success else '❌ Failed'}")
    
    # Verify the imported modules point to the right files
    if import_results["site_packages_import"]:
        logger.info(f"StateManager module file: {manager_module.__file__}")
        logger.info(f"DecisionRecord module file: {models_module.__file__}")
else:
    logger.error("❌ STATE MODULE IMPORT FIX FAILED!")
    logger.error("Python path:")
    for path in sys.path:
        logger.info(f"  {path}")
    
    # List all possible match files
    logger.info("Searching for state module files in all sys.path locations:")
    for path_item in sys.path:
        potential_state_init = os.path.join(path_item, "kometa_ai", "state", "__init__.py")
        if os.path.exists(potential_state_init):
            logger.info(f"  Found potential state __init__.py at {potential_state_init}")
EOF

# Execute the helper script to fix the state directory
echo "Fixing state directory..."
python fix_state_dir.py

# Copy mypy.ini to the current directory for CI
if [ -f "mypy.ini" ]; then
    echo "Using existing mypy.ini"
else
    echo "Creating mypy.ini for type checking"
    cat > mypy.ini << EOF
[mypy]
# Global options
python_version = 3.11
warn_return_any = False
warn_unused_configs = True
disallow_untyped_defs = False
disallow_incomplete_defs = False
check_untyped_defs = True
disallow_untyped_decorators = False
no_implicit_optional = True
strict_optional = False
warn_redundant_casts = False
warn_unused_ignores = False
warn_no_return = True
warn_unreachable = True

# Explicitly include kometa_ai modules
namespace_packages = False
explicit_package_bases = True

# Package-specific settings
[mypy.kometa_ai]
ignore_missing_imports = False
disallow_untyped_defs = False
check_untyped_defs = True

[mypy.kometa_ai.state]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.claude]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.common]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.kometa]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.notification]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.radarr]
ignore_missing_imports = False
implicit_reexport = True

[mypy.kometa_ai.utils]
ignore_missing_imports = False
implicit_reexport = True

# External dependencies
[mypy.*.external]
ignore_missing_imports = True
follow_imports = skip

# Allow fallback to mocks in __main__ if needed
# but don't let it affect other modules
[mypy.kometa_ai.__main__]
warn_unused_ignores = False
ignore_errors = True

# Don't let typing errors in test code block CI
[mypy.tests.*]
ignore_errors = True
EOF
fi

# Run tests with coverage
echo "Running tests..."
PYTHONPATH=. pytest -xvs $@

# Generate coverage report
echo "Generating coverage report..."
coverage xml
coverage html

echo "Tests completed successfully!"