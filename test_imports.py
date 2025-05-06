#!/usr/bin/env python3
"""
Test script to verify module imports are working properly.
This script attempts to import key modules and reports any issues.
"""

import sys
import os
import json
import site
import subprocess
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('import_test_results.log')
    ]
)
logger = logging.getLogger("import_test")

# Create a test summary
test_summary = {
    "python_version": sys.version,
    "test_timestamp": None,
    "environment_check": {},
    "directory_checks": {},
    "import_results": {},
    "site_packages_check": {},
    "mocked_module_check": {},
    "dynamic_fix_results": {},
    "final_status": "UNKNOWN"
}

def log_json(obj: Any) -> None:
    """Log an object as formatted JSON."""
    logger.info(json.dumps(obj, indent=2, default=str))

# Add current directory to Python path
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))
logger.info(f"Added {root_dir} to sys.path")

# Print Python version and path
logger.info(f"Python version: {sys.version}")
logger.info(f"sys.path: {sys.path}")
test_summary["python_version"] = sys.version

# Check environment variables that might affect Python imports
env_vars_to_check = [
    "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "CONDA_PREFIX", 
    "PWD", "PATH", "CI", "SKIP_PRODUCTION_TESTS"
]

logger.info("Checking environment variables that might affect imports:")
for var in env_vars_to_check:
    value = os.environ.get(var)
    logger.info(f"  {var}: {value}")
    test_summary["environment_check"][var] = value

# Check if directories exist and are in Python path
def check_directory(dir_path: str) -> Dict[str, Any]:
    """Check if a directory exists and whether it's in Python path."""
    result = {}
    abs_path = os.path.abspath(dir_path)
    logger.info(f"Checking directory: {abs_path}")
    result["abs_path"] = abs_path
    
    if os.path.exists(abs_path):
        logger.info(f"Directory exists: {abs_path}")
        contents = os.listdir(abs_path)
        logger.info(f"Contents: {contents}")
        result["exists"] = True
        result["contents"] = contents
        
        if abs_path in sys.path or dir_path in sys.path:
            logger.info(f"Directory is in Python path")
            result["in_python_path"] = True
        else:
            logger.info(f"Directory is NOT in Python path")
            result["in_python_path"] = False
    else:
        logger.info(f"Directory does not exist: {abs_path}")
        result["exists"] = False
        result["contents"] = []
        result["in_python_path"] = False
    
    return result

# Check site-packages directories 
site_packages_dirs = site.getsitepackages()
logger.info(f"Site-packages directories: {site_packages_dirs}")
test_summary["site_packages_check"]["dirs"] = site_packages_dirs

# Check for kometa_ai and state in site-packages
for site_dir in site_packages_dirs:
    kometa_dir = os.path.join(site_dir, "kometa_ai")
    state_dir = os.path.join(kometa_dir, "state")
    
    if os.path.exists(kometa_dir):
        logger.info(f"Found kometa_ai in site-packages: {kometa_dir}")
        contents = os.listdir(kometa_dir)
        logger.info(f"Contents: {contents}")
        test_summary["site_packages_check"][kometa_dir] = {
            "exists": True,
            "contents": contents,
            "has_py_typed": "py.typed" in contents,
            "has_init": "__init__.py" in contents
        }
        
        if os.path.exists(state_dir):
            logger.info(f"Found state dir in site-packages: {state_dir}")
            state_contents = os.listdir(state_dir)
            logger.info(f"State dir contents: {state_contents}")
            test_summary["site_packages_check"][state_dir] = {
                "exists": True,
                "contents": state_contents,
                "has_py_typed": "py.typed" in state_contents,
                "has_init": "__init__.py" in state_contents,
                "has_manager": "manager.py" in state_contents,
                "has_models": "models.py" in state_contents
            }
        else:
            logger.warning(f"No state dir in site-packages at {state_dir}")
            test_summary["site_packages_check"][state_dir] = {
                "exists": False
            }
    else:
        logger.warning(f"No kometa_ai in site-packages at {kometa_dir}")
        test_summary["site_packages_check"][kometa_dir] = {
            "exists": False  
        }

# Check current directory and kometa_ai directory
directories_to_check = [
    ".",
    "./kometa_ai", 
    "./kometa_ai/state",
    "./kometa_ai/claude",
    "./kometa_ai/common",
    "./kometa_ai/kometa",
    "./kometa_ai/notification",
    "./kometa_ai/radarr",
    "./kometa_ai/utils"
]

for dir_path in directories_to_check:
    test_summary["directory_checks"][dir_path] = check_directory(dir_path)

# List all potentially importable Python modules
def find_modules(directory: str) -> List[str]:
    """Find all potential Python modules in a directory."""
    modules = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py") and file != "__pycache__":
                rel_dir = os.path.relpath(root, directory)
                if rel_dir == ".":
                    module_name = file[:-3]  # Remove '.py'
                else:
                    module_name = f"{rel_dir.replace(os.sep, '.')}.{file[:-3]}"
                    if module_name.startswith("."):
                        module_name = module_name[1:]
                modules.append(module_name)
    return modules

logger.info("Searching for Python modules in kometa_ai...")
potential_modules = find_modules("kometa_ai")
logger.info(f"Found modules: {potential_modules}")
test_summary["potential_modules"] = potential_modules

# Try to import each module
modules_to_test = [
    "kometa_ai", 
    "kometa_ai.state", 
    "kometa_ai.state.manager", 
    "kometa_ai.state.models",
    "kometa_ai.claude",
    "kometa_ai.claude.processor",
    "kometa_ai.utils",
    "kometa_ai.utils.logging"
]

# Clear importlib cache to ensure fresh imports
try:
    importlib.invalidate_caches()
    logger.info("Invalidated importlib caches")
except Exception as e:
    logger.warning(f"Failed to invalidate importlib caches: {e}")

for module_name in modules_to_test:
    logger.info(f"Attempting to import {module_name}...")
    test_summary["import_results"][module_name] = {}
    
    try:
        module = importlib.import_module(module_name)
        logger.info(f"Successfully imported {module_name}")
        test_summary["import_results"][module_name]["success"] = True
        
        if hasattr(module, "__file__"):
            logger.info(f"Module file: {module.__file__}")
            test_summary["import_results"][module_name]["file"] = module.__file__
            
        if hasattr(module, "__path__"):
            logger.info(f"Module path: {module.__path__}")
            test_summary["import_results"][module_name]["path"] = module.__path__
            
        # Print dir() to check module contents
        logger.info(f"Module dir(): {dir(module)}")
        test_summary["import_results"][module_name]["dir"] = dir(module)
        
    except ImportError as e:
        logger.error(f"Failed to import {module_name}: {e}")
        test_summary["import_results"][module_name]["success"] = False
        test_summary["import_results"][module_name]["error"] = str(e)
        
        # Try to locate the module file
        spec = importlib.util.find_spec(module_name)
        if spec:
            logger.info(f"Module spec exists: {spec}")
            test_summary["import_results"][module_name]["spec_exists"] = True
            
            if spec.origin:
                logger.info(f"Module origin: {spec.origin}")
                test_summary["import_results"][module_name]["origin"] = spec.origin
        else:
            logger.error(f"Module spec not found for {module_name}")
            test_summary["import_results"][module_name]["spec_exists"] = False

# Check core classes that are used
classes_to_check = [
    ("kometa_ai.state.manager", "StateManager"),
    ("kometa_ai.state.models", "DecisionRecord"),
    ("kometa_ai.claude.processor", "MovieProcessor") 
]

for class_path, class_name in classes_to_check:
    logger.info(f"Checking for class {class_path}.{class_name}")
    test_summary["import_results"][f"{class_path}.{class_name}"] = {}
    
    try:
        module = importlib.import_module(class_path)
        if hasattr(module, class_name):
            cls = getattr(module, class_name)
            logger.info(f"Found class {class_name} in {class_path}")
            logger.info(f"Class details: {cls}")
            test_summary["import_results"][f"{class_path}.{class_name}"]["success"] = True
            test_summary["import_results"][f"{class_path}.{class_name}"]["details"] = str(cls)
        else:
            logger.error(f"Class {class_name} not found in {class_path}")
            test_summary["import_results"][f"{class_path}.{class_name}"]["success"] = False
            test_summary["import_results"][f"{class_path}.{class_name}"]["error"] = f"Class not found in module"
    except ImportError as e:
        logger.error(f"Failed to import {class_path}: {e}")
        test_summary["import_results"][f"{class_path}.{class_name}"]["success"] = False
        test_summary["import_results"][f"{class_path}.{class_name}"]["error"] = str(e)

# Check for conditional import pattern in __main__.py
logger.info("Checking for mocked StateManager in __main__.py...")
try:
    from kometa_ai.__main__ import StateManager as MainStateManager
    logger.info(f"StateManager from __main__: {MainStateManager}")
    
    # Check module import path
    state_manager_module = sys.modules.get('kometa_ai.state.manager')
    logger.info(f"State manager module: {state_manager_module}")
    
    test_summary["mocked_module_check"]["main_state_manager"] = {
        "success": True,
        "module_path": str(state_manager_module),
        "details": str(MainStateManager)
    }
except ImportError as e:
    logger.error(f"Failed to import StateManager from __main__: {e}")
    test_summary["mocked_module_check"]["main_state_manager"] = {
        "success": False, 
        "error": str(e)
    }

# Try dynamically fixing the issue and verify
logger.info("\n===== Attempting dynamic fixes =====")

# Create a fix script similar to what we'd use in CI
fix_script = """
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
        "\"\"\"kometa-ai package.\"\"\"\n",
    os.path.join(kometa_dir, "py.typed"): 
        "",
    os.path.join(state_dir, "__init__.py"): 
        "\"\"\"State management module.\"\"\"\n\nfrom kometa_ai.state.manager import StateManager\nfrom kometa_ai.state.models import DecisionRecord\n\n__all__ = [\"StateManager\", \"DecisionRecord\"]\n",
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
"""

# Write and execute the fix script
fix_script_path = os.path.join(os.getcwd(), "dynamic_fix.py")
with open(fix_script_path, "w") as f:
    f.write(fix_script)

logger.info(f"Running dynamic fix script: {fix_script_path}")
try:
    result = subprocess.run([sys.executable, fix_script_path], 
                            capture_output=True, text=True, check=False)
    test_summary["dynamic_fix_results"]["returncode"] = result.returncode
    test_summary["dynamic_fix_results"]["stdout"] = result.stdout
    test_summary["dynamic_fix_results"]["stderr"] = result.stderr
    
    logger.info(f"Fix script return code: {result.returncode}")
    logger.info(f"Fix script output:\n{result.stdout}")
    if result.stderr:
        logger.error(f"Fix script errors:\n{result.stderr}")
    
    worked = result.returncode == 0
    logger.info(f"Dynamic fix {'succeeded' if worked else 'failed'}")
    test_summary["dynamic_fix_results"]["success"] = worked
    
    # Try imports after fix
    if worked:
        try:
            # Clear cache again
            importlib.invalidate_caches()
            
            # Try to import state module
            from kometa_ai.state.manager import StateManager
            from kometa_ai.state.models import DecisionRecord
            
            logger.info("Successfully imported from kometa_ai.state after fix!")
            test_summary["dynamic_fix_results"]["post_fix_import"] = True
        except ImportError as e:
            logger.error(f"Still can't import state modules after fix: {e}")
            test_summary["dynamic_fix_results"]["post_fix_import"] = False
            test_summary["dynamic_fix_results"]["post_fix_error"] = str(e)
    
except Exception as e:
    logger.error(f"Error running fix script: {e}")
    test_summary["dynamic_fix_results"]["error"] = str(e)

# Final summary of findings
success_count = sum(1 for mod, result in test_summary["import_results"].items() 
                  if result.get("success", False))
total_tests = len(test_summary["import_results"])

logger.info("\n===== IMPORT TEST SUMMARY =====")
logger.info(f"Total tests: {total_tests}")
logger.info(f"Successful imports: {success_count}")
logger.info(f"Failed imports: {total_tests - success_count}")

dynamic_fix_worked = test_summary["dynamic_fix_results"].get("success", False)
logger.info(f"Dynamic fix successful: {dynamic_fix_worked}")

# Determine overall status
if success_count == total_tests:
    status = "SUCCESS"
elif dynamic_fix_worked:
    status = "FIXED"
else:
    status = "FAILED"

test_summary["final_status"] = status
logger.info(f"Final status: {status}")

# Write full results as JSON
with open("import_test_results.json", "w") as f:
    json.dump(test_summary, f, indent=2, default=str)
logger.info("Full test results written to import_test_results.json")

logger.info("Import test completed")