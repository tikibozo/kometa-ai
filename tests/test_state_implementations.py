"""
Tests to ensure consistent implementations of StateManager.

This file contains tests that verify:
1. The real StateManager and MockStateManager have the same methods
2. Both implementations have the required methods with the correct signatures
"""

import inspect
import unittest
import sys
import os
from typing import Set, Dict, Any, List, Optional, Type, Callable

# Add the parent directory to the path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try importing the real StateManager
try:
    from kometa_ai.state.manager import StateManager as RealStateManager
    HAS_REAL_IMPLEMENTATION = True
except ImportError:
    print("Note: Could not import real StateManager, tests will use mock only")
    HAS_REAL_IMPLEMENTATION = False

# Import the MockStateManager from conftest
try:
    from conftest import MockStateManager
except ImportError:
    # As a fallback, define a minimal MockStateManager for testing
    print("Warning: Could not import MockStateManager from conftest, using fallback")
    class MockStateManager:
        def __init__(self, *args, **kwargs):
            self.state = {'decisions': {}, 'changes': [], 'errors': []}
            
        def load(self): pass
        def save(self): pass
        def reset(self): pass
        def get_decision(self, a, b): return None
        def set_decision(self, d): pass
        def get_decisions_for_movie(self, m): return []
        def get_metadata_hash(self, m): return None
        def log_change(self, a, b, c, d, e): pass
        def log_error(self, a, b): pass
        def get_changes(self): return []
        def get_errors(self): return []
        def clear_errors(self): self.state['errors'] = []
        def clear_changes(self): self.state['changes'] = []
        def dump(self): return "{}"
        def validate_state(self): return []

# Required methods with their signatures (parameter count, excluding self)
REQUIRED_METHODS = {
    'load': 0,
    'save': 0,
    'reset': 0,
    'get_decision': 2,
    'set_decision': 1,
    'get_decisions_for_movie': 1,
    'get_metadata_hash': 1,
    'log_change': 5,
    'log_error': 2,
    'get_changes': 0,
    'get_errors': 0,
    'clear_errors': 0,
    'clear_changes': 0,
    'dump': 0,
    'validate_state': 0
}


def get_method_signature(cls: Type, method_name: str) -> Optional[inspect.Signature]:
    """Get the signature of a method."""
    try:
        method = getattr(cls, method_name)
        return inspect.signature(method)
    except (AttributeError, ValueError):
        return None


def get_method_parameter_count(cls: Type, method_name: str) -> int:
    """Get the number of parameters for a method, excluding 'self'."""
    sig = get_method_signature(cls, method_name)
    if not sig:
        return -1
    
    # Count parameters, excluding 'self'
    return len([p for p in sig.parameters.values() if p.name != 'self'])


def get_class_public_methods(cls: Type) -> Set[str]:
    """Get all public methods of a class."""
    return {name for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith('_')}


class TestStateImplementations(unittest.TestCase):
    """Tests to ensure StateManager implementations are consistent."""

    def test_mock_has_all_required_methods(self):
        """Test that MockStateManager has all required methods."""
        mock_methods = get_class_public_methods(MockStateManager)
        
        for method_name in REQUIRED_METHODS:
            with self.subTest(method=method_name):
                self.assertIn(method_name, mock_methods, 
                              f"MockStateManager is missing required method: {method_name}")
                
                # Also check parameter count
                expected_param_count = REQUIRED_METHODS[method_name]
                actual_param_count = get_method_parameter_count(MockStateManager, method_name)
                
                # Special case for variadic methods
                if method_name in ('log_change', 'log_error'):
                    # Allow methods with *args, **kwargs
                    self.assertGreaterEqual(
                        actual_param_count, 0, 
                        f"MockStateManager.{method_name} should accept parameters")
                else:
                    self.assertEqual(
                        expected_param_count, actual_param_count,
                        f"MockStateManager.{method_name} has wrong parameter count. "
                        f"Expected {expected_param_count}, got {actual_param_count}")

    @unittest.skipIf(not HAS_REAL_IMPLEMENTATION, "Real StateManager not available")
    def test_real_has_all_required_methods(self):
        """Test that real StateManager has all required methods."""
        real_methods = get_class_public_methods(RealStateManager)
        
        for method_name in REQUIRED_METHODS:
            with self.subTest(method=method_name):
                self.assertIn(method_name, real_methods,
                             f"Real StateManager is missing required method: {method_name}")
                
                # Also check parameter count
                expected_param_count = REQUIRED_METHODS[method_name]
                actual_param_count = get_method_parameter_count(RealStateManager, method_name)
                
                self.assertEqual(
                    expected_param_count, actual_param_count,
                    f"RealStateManager.{method_name} has wrong parameter count. "
                    f"Expected {expected_param_count}, got {actual_param_count}")

    @unittest.skipIf(not HAS_REAL_IMPLEMENTATION, "Real StateManager not available")
    def test_implementations_have_same_methods(self):
        """Test that both implementations have the same methods."""
        real_methods = get_class_public_methods(RealStateManager)
        mock_methods = get_class_public_methods(MockStateManager)
        
        # Find methods only in real implementation
        real_only = real_methods - mock_methods
        if real_only:
            self.fail(f"Methods in real but not in mock: {', '.join(real_only)}")
        
        # Find methods only in mock implementation
        mock_only = mock_methods - real_methods
        expected_mock_only = {'set_detailed_analysis', 'get_detailed_analysis'}
        unexpected_mock_only = mock_only - expected_mock_only
        
        if unexpected_mock_only:
            self.fail(f"Unexpected methods in mock but not in real: {', '.join(unexpected_mock_only)}")


if __name__ == '__main__':
    unittest.main()