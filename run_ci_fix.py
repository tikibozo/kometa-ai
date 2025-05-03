#!/usr/bin/env python3
"""
Script to run the CI fix for state module issues.
This script is a wrapper around the CI fix that can be called directly
in CI environments to avoid shell script execution issues.
"""

import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ci_fix.log')
    ]
)
logger = logging.getLogger("run_ci_fix")

def run_command(cmd, description=None):
    """Run a shell command and log the output."""
    if description:
        logger.info(f"Running: {description}")
    else:
        logger.info(f"Running command: {cmd}")
    
    try:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        exit_code = process.returncode
        
        logger.info(f"Command exit code: {exit_code}")
        if stdout:
            logger.info(f"Command output:\n{stdout}")
        if stderr:
            logger.warning(f"Command stderr:\n{stderr}")
            
        return exit_code == 0, stdout, stderr
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False, "", str(e)

def run_pre_build_setup():
    """Run the pre-build setup script."""
    logger.info("Running pre-build setup...")
    # Make sure the script is executable
    run_command("chmod +x ./scripts/pre_build_setup.sh", "Making pre_build_setup.sh executable")
    # Run the script
    success, stdout, stderr = run_command("./scripts/pre_build_setup.sh", "Running pre_build_setup.sh")
    return success

def run_state_module_fix():
    """Run the state module fix script."""
    logger.info("Running state module fix...")
    # Make sure the script is executable
    run_command("chmod +x ./ci_fix_state_module.py", "Making ci_fix_state_module.py executable")
    # Run the script
    success, stdout, stderr = run_command("python3 ./ci_fix_state_module.py", "Running ci_fix_state_module.py")
    return success

def install_package():
    """Install the package in development mode."""
    logger.info("Installing package in development mode...")
    success, stdout, stderr = run_command("pip install -e . --verbose", "Installing package in development mode")
    return success

def verify_state_module():
    """Verify that the state module can be imported."""
    logger.info("Verifying state module can be imported...")
    try:
        # Create a temporary Python script to test imports
        with open("verify_imports.py", "w") as f:
            f.write("""
import importlib
import sys
import os

print("Python version:", sys.version)
print("Python path:", sys.path)

try:
    importlib.invalidate_caches()
    from kometa_ai.state import StateManager, DecisionRecord
    print("Successfully imported StateManager:", StateManager)
    print("Successfully imported DecisionRecord:", DecisionRecord)
    
    # Create a StateManager instance to verify it works
    state_dir = os.path.join(os.getcwd(), "test_state")
    os.makedirs(state_dir, exist_ok=True)
    state_manager = StateManager(state_dir)
    print("Successfully created StateManager instance:", state_manager)
    
    sys.exit(0)  # Success
except Exception as e:
    print("Error importing state module:", e)
    sys.exit(1)  # Failure
""")
        
        # Run the verification script
        success, stdout, stderr = run_command("python3 verify_imports.py", "Running verification script")
        return success
    except Exception as e:
        logger.error(f"Error creating verification script: {e}")
        return False

def run_tests():
    """Run the tests."""
    logger.info("Running tests...")
    success, stdout, stderr = run_command("pytest -xvs tests/test_state_manager.py", "Running state manager tests")
    return success

def main():
    """Main function."""
    logger.info("Starting CI fix for state module issues...")
    
    # Run pre-build setup
    if not run_pre_build_setup():
        logger.error("Pre-build setup failed, but continuing...")
    
    # Run state module fix
    if not run_state_module_fix():
        logger.error("State module fix failed, but continuing...")
    
    # Install the package
    if not install_package():
        logger.error("Package installation failed, but continuing...")
    
    # Verify state module
    if verify_state_module():
        logger.info("✅ State module imports are working!")
    else:
        logger.error("❌ State module imports are still not working")
    
    # Run tests if requested
    if "--test" in sys.argv:
        if run_tests():
            logger.info("✅ Tests passed!")
        else:
            logger.error("❌ Tests failed")
    
    logger.info("CI fix completed!")

if __name__ == "__main__":
    main()