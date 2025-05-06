#!/usr/bin/env python3
"""
Verification script for state module.
Checks that the state module has all required methods and attributes.
"""

import os
import sys
import importlib
import inspect
import logging
from typing import List, Set, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("verify_state_module")

# Required methods that must exist in the StateManager class
REQUIRED_METHODS = {
    'load',
    'save',
    'reset',
    'get_decision',
    'set_decision',
    'get_decisions_for_movie',
    'get_metadata_hash',
    'log_change',
    'log_error',
    'get_changes',
    'get_errors',
    'clear_errors',
    'clear_changes',
    'dump'
}

def verify_state_manager() -> bool:
    """Verify that the StateManager class has all required methods."""
    try:
        # Try to import the state module
        from kometa_ai.state import StateManager
        logger.info(f"Successfully imported StateManager from kometa_ai.state")
        
        # Check if all required methods exist
        missing_methods = []
        for method_name in REQUIRED_METHODS:
            if not hasattr(StateManager, method_name):
                missing_methods.append(method_name)
        
        if missing_methods:
            logger.error(f"StateManager is missing the following required methods: {', '.join(missing_methods)}")
            return False
        
        # If we get here, all required methods exist
        logger.info(f"StateManager has all required methods: {', '.join(REQUIRED_METHODS)}")
        return True
    
    except ImportError as e:
        logger.error(f"Failed to import StateManager: {e}")
        return False
    except Exception as e:
        logger.error(f"Error verifying StateManager: {e}")
        return False

def main() -> int:
    """Main function."""
    logger.info("Verifying state module...")
    
    # Verify StateManager
    if verify_state_manager():
        logger.info("✅ StateManager verification successful")
        return 0
    else:
        logger.error("❌ StateManager verification failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())