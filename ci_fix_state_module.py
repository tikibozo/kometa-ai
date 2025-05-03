#!/usr/bin/env python3
"""
CI fix for the state module import issues.

This script addresses the root cause of import errors with kometa_ai.state module
in CI environments by ensuring all module files are properly installed and importable.
"""

import os
import sys
import shutil
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('state_module_fix.log')
    ]
)
logger = logging.getLogger("state_module_fix")

def diagnose_environment() -> Dict[str, Any]:
    """Diagnose the Python environment for import issues."""
    results = {
        "python_version": sys.version,
        "python_path": sys.path,
        "cwd": os.getcwd(),
    }
    
    # Check if we're in a CI environment
    results["is_ci"] = os.environ.get("CI", "False").lower() in ("true", "1", "yes")
    
    # Get site-packages directories
    import site
    site_packages = site.getsitepackages()
    results["site_packages"] = site_packages
    
    return results


def check_module_structure(module_dirs: List[str] = None) -> Dict[str, Any]:
    """Check the kometa_ai module structure, focusing on the state module."""
    if module_dirs is None:
        module_dirs = [os.getcwd()]
    
    results = {}
    
    for base_dir in module_dirs:
        # Check for source code structure
        kometa_dir = os.path.join(base_dir, "kometa_ai")
        state_dir = os.path.join(kometa_dir, "state")
        
        if not os.path.exists(kometa_dir):
            logger.warning(f"No kometa_ai directory found at {kometa_dir}")
            continue
            
        results[kometa_dir] = {
            "exists": True,
            "contents": os.listdir(kometa_dir),
            "has_init": os.path.exists(os.path.join(kometa_dir, "__init__.py")),
            "has_py_typed": os.path.exists(os.path.join(kometa_dir, "py.typed")),
        }
        
        if os.path.exists(state_dir):
            results[state_dir] = {
                "exists": True,
                "contents": os.listdir(state_dir),
                "has_init": os.path.exists(os.path.join(state_dir, "__init__.py")),
                "has_py_typed": os.path.exists(os.path.join(state_dir, "py.typed")),
                "has_manager": os.path.exists(os.path.join(state_dir, "manager.py")),
                "has_models": os.path.exists(os.path.join(state_dir, "models.py")),
            }
        else:
            logger.warning(f"No state directory found at {state_dir}")
            results[state_dir] = {"exists": False}
    
    return results


def ensure_py_typed_files(base_dir: str) -> None:
    """Ensure py.typed files exist in all packages."""
    packages = [
        "kometa_ai",
        "kometa_ai/state",
        "kometa_ai/claude",
        "kometa_ai/common",
        "kometa_ai/kometa",
        "kometa_ai/notification",
        "kometa_ai/radarr",
        "kometa_ai/utils"
    ]
    
    for pkg in packages:
        pkg_path = os.path.join(base_dir, pkg)
        # Create directory if it doesn't exist
        if not os.path.exists(pkg_path):
            os.makedirs(pkg_path, exist_ok=True)
            logger.info(f"Created directory {pkg_path}")
            
            # Create __init__.py if needed
            init_file = os.path.join(pkg_path, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    f.write('"""Auto-generated package init."""\n')
                logger.info(f"Created __init__.py at {init_file}")
        
        # Create py.typed file
        py_typed_path = os.path.join(pkg_path, "py.typed")
        with open(py_typed_path, "w") as f:
            pass  # Create empty file
        logger.info(f"Created/ensured py.typed file at {py_typed_path}")


def fix_site_packages(diag_results: Dict[str, Any]) -> bool:
    """Fix the state module in site-packages locations."""
    if not diag_results["site_packages"]:
        logger.error("No site-packages directories found")
        return False
    
    # Get the current directory for source files
    src_dir = os.getcwd()
    src_state_dir = os.path.join(src_dir, "kometa_ai", "state")
    
    if not os.path.exists(src_state_dir):
        logger.error(f"Source state directory not found at {src_state_dir}")
        return False
    
    success = False
    
    for site_pkg in diag_results["site_packages"]:
        logger.info(f"Fixing state module in {site_pkg}")
        
        # Create kometa_ai directory if it doesn't exist
        kometa_dir = os.path.join(site_pkg, "kometa_ai")
        os.makedirs(kometa_dir, exist_ok=True)
        
        # Ensure kometa_ai/__init__.py exists
        kometa_init = os.path.join(kometa_dir, "__init__.py")
        if not os.path.exists(kometa_init):
            with open(kometa_init, "w") as f:
                f.write('"""kometa-ai package for Claude integration with Radarr."""\n')
            logger.info(f"Created {kometa_init}")
        
        # Create py.typed file for the main package
        kometa_py_typed = os.path.join(kometa_dir, "py.typed")
        with open(kometa_py_typed, "w") as f:
            pass  # Empty file
        logger.info(f"Created {kometa_py_typed}")
        
        # Create state directory
        state_dir = os.path.join(kometa_dir, "state")
        os.makedirs(state_dir, exist_ok=True)
        
        # Copy state module files
        for filename in ["__init__.py", "manager.py", "models.py"]:
            src_file = os.path.join(src_state_dir, filename)
            dest_file = os.path.join(state_dir, filename)
            
            if os.path.exists(src_file):
                shutil.copyfile(src_file, dest_file)
                logger.info(f"Copied {filename} to {dest_file}")
            else:
                logger.warning(f"Source file {src_file} not found")
                
                # Create basic __init__.py if needed
                if filename == "__init__.py":
                    with open(dest_file, "w") as f:
                        f.write('''"""
State management for Kometa-AI.

This package provides functionality for persisting decisions and state.
"""

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ['StateManager', 'DecisionRecord']
''')
                    logger.info(f"Created {dest_file}")
        
        # Create py.typed for state module
        state_py_typed = os.path.join(state_dir, "py.typed")
        with open(state_py_typed, "w") as f:
            pass  # Empty file
        logger.info(f"Created {state_py_typed}")
        
        success = True
    
    return success


def verify_imports() -> bool:
    """Verify that imports are working properly now."""
    # Clear importlib cache to ensure fresh imports
    importlib.invalidate_caches()
    logger.info("Cleared importlib cache")
    
    try:
        # Try to import state module
        logger.info("Testing state module imports...")
        from kometa_ai.state import StateManager, DecisionRecord
        
        logger.info(f"Successfully imported StateManager: {StateManager}")
        logger.info(f"Successfully imported DecisionRecord: {DecisionRecord}")
        
        # Check module file paths
        state_module = sys.modules.get("kometa_ai.state")
        if state_module and hasattr(state_module, "__file__"):
            logger.info(f"kometa_ai.state module file: {state_module.__file__}")
        
        manager_module = sys.modules.get("kometa_ai.state.manager")
        if manager_module and hasattr(manager_module, "__file__"):
            logger.info(f"kometa_ai.state.manager module file: {manager_module.__file__}")
        
        return True
    except ImportError as e:
        logger.error(f"Import verification failed: {e}")
        return False


def main() -> int:
    """Main function to fix state module import issues."""
    logger.info("Starting state module fix for CI environment")
    
    # Step 1: Diagnose environment
    logger.info("Diagnosing environment...")
    diag_results = diagnose_environment()
    logger.info(f"Python version: {diag_results['python_version']}")
    logger.info(f"Working directory: {diag_results['cwd']}")
    logger.info(f"CI environment: {diag_results['is_ci']}")
    
    # Step 2: Check module structure
    logger.info("Checking module structure...")
    module_check = check_module_structure([diag_results['cwd']] + diag_results['site_packages'])
    
    # Step 3: Fix site-packages installations
    logger.info("Fixing site-packages...")
    site_fixed = fix_site_packages(diag_results)
    if site_fixed:
        logger.info("Site-packages fix applied")
    else:
        logger.warning("Site-packages fix failed")
    
    # Step 4: Ensure py.typed files exist in all packages
    logger.info("Ensuring py.typed files exist...")
    ensure_py_typed_files(diag_results['cwd'])
    
    # Step 5: Verify imports are working
    logger.info("Verifying imports...")
    imports_working = verify_imports()
    
    if imports_working:
        logger.info("✅ Fix successful: State module imports are working!")
        return 0
    else:
        logger.error("❌ Fix failed: State module imports still not working")
        return 1


if __name__ == "__main__":
    sys.exit(main())