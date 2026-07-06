"""
Test configuration for pytest.
Ensures that the kometa_ai package can be imported properly.
"""

import sys
from pathlib import Path

# Make the repository root importable so `kometa_ai` and `test_data` resolve
# even when the package isn't installed.
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Fail fast if the package can't be imported -- no mock fallbacks.
from kometa_ai.state.manager import StateManager  # noqa: E402,F401
from kometa_ai.state.models import DecisionRecord  # noqa: E402,F401
from kometa_ai.claude.processor import MovieProcessor  # noqa: E402,F401
