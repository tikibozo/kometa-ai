
import os
import sys
import shutil
import importlib
from pathlib import Path

# Get site packages
import site
site_packages = site.getsitepackages()[0]
print(f"Site packages: {site_packages}")

# Ensure kometa_ai directory exists
kometa_dir = os.path.join(site_packages, "kometa_ai")
os.makedirs(kometa_dir, exist_ok=True)

# Ensure state directory exists
state_dir = os.path.join(kometa_dir, "state")
os.makedirs(state_dir, exist_ok=True)

# Create files if they don't exist
files_to_create = {
    os.path.join(kometa_dir, "__init__.py"): 
        """"kometa-ai package."""
",
    os.path.join(kometa_dir, "py.typed"): 
        "",
    os.path.join(state_dir, "__init__.py"): 
        """"State management module."""

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ["StateManager", "DecisionRecord"]
",
    os.path.join(state_dir, "py.typed"): 
        ""
}

for file_path, content in files_to_create.items():
    with open(file_path, 'w') as f:
        f.write(content)
    print(f"Created/updated {file_path}")

# Copy state module files
src_dir = os.path.join(os.getcwd(), "kometa_ai", "state")
for filename in ["manager.py", "models.py"]:
    src_file = os.path.join(src_dir, filename)
    dst_file = os.path.join(state_dir, filename)
    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {filename} to {dst_file}")

# Clear importlib cache
importlib.invalidate_caches()
print("Importlib caches invalidated")

# Try imports
try:
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    print("Success: Dynamic fix worked!")
    print(f"StateManager: {StateManager}")
    print(f"DecisionRecord: {DecisionRecord}")
    exit(0)
except ImportError as e:
    print(f"Failed: {e}")
    exit(1)
