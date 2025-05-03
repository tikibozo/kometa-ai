"""
Test configuration for pytest.
Ensures that the kometa_ai package can be imported properly.
"""

import sys
import os
from pathlib import Path

# Add the root directory to PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Import the modules to ensure they can be found
# during test collection
try:
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    from kometa_ai.claude.processor import MovieProcessor
except ImportError as e:
    print(f"Failed to import module: {e}")
    raise