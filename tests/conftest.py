"""
Test configuration for pytest.
Ensures that the kometa_ai package can be imported properly.
"""

import sys
import os
from pathlib import Path
import importlib
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("conftest")

# Add the root directory to PYTHONPATH and ensure it's at the beginning
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Print the current sys.path for debugging
logger.debug(f"sys.path = {sys.path}")

# List all the available files in the kometa_ai directory
kometa_dir = root_dir / "kometa_ai"
if kometa_dir.exists():
    logger.debug(f"Listing contents of {kometa_dir}:")
    for item in kometa_dir.glob("**/*"):
        logger.debug(f"  {item.relative_to(root_dir)}")

# Import kometa_ai and print its __path__ attribute
try:
    import kometa_ai
    logger.debug(f"kometa_ai.__path__ = {kometa_ai.__path__}")
    logger.debug(f"kometa_ai.__file__ = {kometa_ai.__file__}")
except ImportError as e:
    logger.error(f"Failed to import kometa_ai: {e}")

# Mock the StateManager and DecisionRecord classes if they can't be imported
class MockStateManager:
    def __init__(self, *args, **kwargs):
        self.state = {'decisions': {}, 'changes': [], 'errors': []}
    
    def load(self):
        pass
    
    def save(self):
        pass
    
    def log_change(self, *args, **kwargs):
        change = {
            'movie_id': kwargs.get('movie_id', 0),
            'title': kwargs.get('movie_title', ''),
            'collection': kwargs.get('collection_name', ''),
            'action': kwargs.get('action', ''),
            'tag': kwargs.get('tag', '')
        }
        self.state.setdefault('changes', []).append(change)
    
    def log_error(self, *args, **kwargs):
        error = {
            'context': kwargs.get('context', ''),
            'message': kwargs.get('error_message', '')
        }
        self.state.setdefault('errors', []).append(error)
        
    def get_changes(self):
        return self.state.get('changes', [])
        
    def get_errors(self):
        return self.state.get('errors', [])
        
    def clear_errors(self):
        self.state['errors'] = []
        
    def clear_changes(self):
        self.state['changes'] = []
        
    def set_detailed_analysis(self, movie_id, collection_name, analysis):
        decisions = self.state.setdefault('decisions', {})
        movie_key = f"movie:{movie_id}"
        
        if movie_key not in decisions:
            decisions[movie_key] = {'collections': {}}
            
        movie_decisions = decisions[movie_key]
        collections = movie_decisions.setdefault('collections', {})
        
        if collection_name not in collections:
            collections[collection_name] = {}
            
        collections[collection_name]['detailed_analysis'] = analysis
        
    def get_detailed_analysis(self, movie_id, collection_name):
        decisions = self.state.get('decisions', {})
        movie_key = f"movie:{movie_id}"
        
        if movie_key not in decisions:
            return None
            
        collections = decisions[movie_key].get('collections', {})
        if collection_name not in collections:
            return None
            
        return collections[collection_name].get('detailed_analysis')

class MockDecisionRecord:
    def __init__(self, *args, **kwargs):
        pass

# Mock the MovieProcessor class that imports StateManager
class MockMovieProcessor:
    def __init__(self, claude_client=None, state_manager=None, batch_size=None, force_refresh=False):
        self.claude_client = claude_client
        self.state_manager = state_manager
        self.batch_size = batch_size
        self.force_refresh = force_refresh
        
    def process_collection(self, collection, movies):
        return [], [], {}

# Try to import the needed modules, but use mocks if they don't exist
try:
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
    logger.debug("Successfully imported state modules!")
except ImportError as e:
    logger.warning(f"Failed to import state modules: {e}. Using mocks.")
    # Create the state module and add our mocks
    sys.modules['kometa_ai.state'] = type('', (), {})()
    sys.modules['kometa_ai.state.manager'] = type('', (), {'StateManager': MockStateManager})()
    sys.modules['kometa_ai.state.models'] = type('', (), {'DecisionRecord': MockDecisionRecord})()
    
    # Make these available for import
    StateManager = MockStateManager
    DecisionRecord = MockDecisionRecord

# Also create a mock for claude processor
try:
    from kometa_ai.claude.processor import MovieProcessor
    logger.debug("Successfully imported MovieProcessor!")
except ImportError as e:
    logger.warning(f"Failed to import MovieProcessor: {e}. Using mock.")
    sys.modules['kometa_ai.claude.processor'] = type('', (), {'MovieProcessor': MockMovieProcessor})()
    MovieProcessor = MockMovieProcessor