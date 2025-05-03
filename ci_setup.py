#!/usr/bin/env python3
"""
CI Setup Script for Kometa-AI.

This script consolidates various CI setup tasks into a single script:
1. Fixes the state module import issues by ensuring all necessary files exist
2. Creates test data needed for CI testing

Usage:
    python ci_setup.py [--test-data] [--state-module] [--verbose]

Options:
    --test-data     Create test data only
    --state-module  Fix state module only
    --verbose       Enable verbose logging
    
If no options are provided, all tasks will be performed.
"""

import os
import sys
import json
import shutil
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ci_setup.log')
    ]
)
logger = logging.getLogger("ci_setup")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CI Setup Script for Kometa-AI")
    parser.add_argument("--test-data", action="store_true", help="Create test data only")
    parser.add_argument("--state-module", action="store_true", help="Fix state module only")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()

# ---- TEST DATA CREATION FUNCTIONS ----

def create_test_data():
    """Create the test data files needed for testing."""
    logger.info("Creating test data...")
    test_dir = Path.cwd() / "test_data"
    
    # Create directory if it doesn't exist
    if not test_dir.exists():
        test_dir.mkdir(parents=True)
        logger.info(f"Created test_data directory at {test_dir}")
    
    # Create __init__.py
    init_file = test_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write('"""Test data for Kometa-AI."""\n')
        logger.info(f"Created {init_file}")
    
    # Sample movie data
    synthetic_movies = [
        {
            "id": 1001,
            "title": "The Adventure Quest",
            "year": 2020,
            "overview": "A group of friends embark on an epic adventure to find a hidden treasure.",
            "genres": ["Adventure", "Action", "Fantasy"],
            "tagline": "The greatest adventure awaits",
            "runtime": 124,
            "rating": 7.8,
            "director": "Jane Smith",
            "actors": ["John Doe", "Sarah Johnson", "Mike Williams"],
            "studio": "Adventure Studios"
        },
        {
            "id": 1002,
            "title": "Mystery in the Dark",
            "year": 2018,
            "overview": "A detective investigates a series of mysterious disappearances in a small town.",
            "genres": ["Mystery", "Thriller", "Crime"],
            "tagline": "The truth lies in the shadows",
            "runtime": 112,
            "rating": 8.2,
            "director": "Robert Brown",
            "actors": ["Emily Clark", "David Wilson", "Linda Martin"],
            "studio": "Enigma Pictures"
        },
        {
            "id": 1003,
            "title": "Laugh Out Loud",
            "year": 2021,
            "overview": "A stand-up comedian tries to make it big while dealing with personal challenges.",
            "genres": ["Comedy", "Drama"],
            "tagline": "Sometimes life is the best punchline",
            "runtime": 98,
            "rating": 7.5,
            "director": "Michael Johnson",
            "actors": ["Lisa Adams", "Tom Clark", "Kevin White"],
            "studio": "Funny Films"
        }
    ]
    
    # Sample collection data
    synthetic_collections = [
        {
            "name": "Adventure Films",
            "description": "Movies focused on exciting journeys, quests, and exploration.",
            "criteria": "Movies with adventure themes, often featuring quests, journeys, or exploration into unknown territories.",
            "tag": "adventure-films",
            "enabled": True
        },
        {
            "name": "Mystery Thrillers",
            "description": "Suspenseful movies with mystery elements.",
            "criteria": "Films that combine mystery and thriller elements, featuring investigations, suspense, and plot twists.",
            "tag": "mystery-thrillers",
            "enabled": True
        },
        {
            "name": "Comedy Collection",
            "description": "Funny movies to lighten the mood.",
            "criteria": "Movies intended to make the audience laugh through humor, amusing situations, and comedy.",
            "tag": "comedy-collection",
            "enabled": True
        }
    ]
    
    # Write JSON files
    movies_file = test_dir / "synthetic_movies.json"
    collections_file = test_dir / "synthetic_collections.json"
    
    with open(movies_file, "w") as f:
        json.dump(synthetic_movies, f, indent=2)
    logger.info(f"Created {movies_file}")
    
    with open(collections_file, "w") as f:
        json.dump(synthetic_collections, f, indent=2)
    logger.info(f"Created {collections_file}")
    
    # Create Python module
    module_file = test_dir / "synthetic_movies.py"
    with open(module_file, "w") as f:
        f.write('''"""
Synthetic test data for movies and collections.
This module provides sample data for testing without requiring external APIs.
"""

from typing import Dict, List, Any

# Sample synthetic movies with metadata
synthetic_movies = {movies}

# Sample collection definitions
synthetic_collections = {collections}
'''.format(
            movies=json.dumps(synthetic_movies, indent=4),
            collections=json.dumps(synthetic_collections, indent=4)
        ))
    logger.info(f"Created {module_file}")
    
    # Ensure config directory exists
    config_dir = Path.cwd() / "kometa-config"
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
        logger.info(f"Created config directory at {config_dir}")
        
    # Copy example config if needed
    example_config = Path.cwd() / "config-examples" / "basic-collections.yml"
    target_config = config_dir / "collections.yml"
    if not target_config.exists() and example_config.exists():
        shutil.copy2(example_config, target_config)
        logger.info(f"Copied example config to {target_config}")
    
    logger.info("Test data creation completed")
    
    # List all files
    logger.info("Test data files created:")
    for file in test_dir.glob("*"):
        logger.info(f"  {file}")
    
    return True

# ---- STATE MODULE FIX FUNCTIONS ----

def diagnose_environment() -> Dict[str, Any]:
    """Diagnose the Python environment for import issues."""
    logger.info("Diagnosing environment...")
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
    
    logger.info(f"Python version: {results['python_version']}")
    logger.info(f"Working directory: {results['cwd']}")
    logger.info(f"CI environment: {results['is_ci']}")
    logger.info(f"Site packages: {results['site_packages']}")
    
    return results


def ensure_py_typed_files(base_dir: str) -> None:
    """Ensure py.typed files exist in all packages."""
    logger.info("Ensuring py.typed files exist...")
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
                    f.write('# Auto-generated package init.\n')
                logger.info(f"Created __init__.py at {init_file}")
        
        # Create py.typed file
        py_typed_path = os.path.join(pkg_path, "py.typed")
        with open(py_typed_path, "w") as f:
            pass  # Create empty file
        logger.info(f"Created/ensured py.typed file at {py_typed_path}")


def find_source_files(base_dir: str) -> Dict[str, Dict[str, str]]:
    """Find source state module files in the current directory."""
    logger.info("Finding source files...")
    source_files = {}
    
    # Define the files we're looking for
    state_files = {
        "__init__": os.path.join(base_dir, "kometa_ai", "state", "__init__.py"),
        "manager": os.path.join(base_dir, "kometa_ai", "state", "manager.py"),
        "models": os.path.join(base_dir, "kometa_ai", "state", "models.py"),
    }
    
    # Check if files exist and if they do, read them
    for name, path in state_files.items():
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    content = f.read()
                source_files[name] = {
                    "path": path,
                    "content": content,
                    "exists": True
                }
                logger.info(f"Found source file for {name}: {path}")
            except Exception as e:
                logger.warning(f"Error reading source file {path}: {e}")
                source_files[name] = {
                    "path": path,
                    "content": "",
                    "exists": True,
                    "error": str(e)
                }
        else:
            logger.warning(f"Source file not found: {path}")
            source_files[name] = {
                "path": path,
                "content": "",
                "exists": False
            }
    
    return source_files


def fix_site_packages(diag_results: Dict[str, Any]) -> bool:
    """Fix the state module in site-packages locations."""
    logger.info("Fixing state module in site-packages...")
    if not diag_results["site_packages"]:
        logger.error("No site-packages directories found")
        return False
    
    # Get the current directory for source files
    src_dir = os.getcwd()
    
    # Check for source files
    source_files = find_source_files(src_dir)
    
    # Hardcoded implementations of the state module files (used as fallback)
    state_init_code = """# State management for Kometa-AI.
# This package provides functionality for persisting decisions and state.

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ['StateManager', 'DecisionRecord']
"""
    
    state_models_code = """from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, UTC


@dataclass
class DecisionRecord:
    """Record of a decision for a movie/collection pair."""

    movie_id: int
    collection_name: str
    include: bool
    confidence: float
    metadata_hash: str
    tag: str
    timestamp: str  # ISO format
    reasoning: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DecisionRecord':
        """Create a DecisionRecord from a dictionary.

        Args:
            data: Dictionary representation

        Returns:
            DecisionRecord object
        """
        return cls(
            movie_id=data.get('movie_id', 0),
            collection_name=data.get('collection_name', ''),
            include=data.get('include', False),
            confidence=data.get('confidence', 0.0),
            metadata_hash=data.get('metadata_hash', ''),
            tag=data.get('tag', ''),
            timestamp=data.get('timestamp', datetime.now(UTC).isoformat()),
            reasoning=data.get('reasoning')
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary.

        Returns:
            Dictionary representation
        """
        result = {
            'movie_id': self.movie_id,
            'collection_name': self.collection_name,
            'include': self.include,
            'confidence': self.confidence,
            'metadata_hash': self.metadata_hash,
            'tag': self.tag,
            'timestamp': self.timestamp
        }

        if self.reasoning:
            result['reasoning'] = self.reasoning

        return result
"""
    
    # Manager code is extensive, let's use what's in the source files if available
    # or copy from pre_build_setup.sh if it exists
    state_manager_code = source_files.get("manager", {}).get("content", "")
    if not state_manager_code:
        # Look for pre_build_setup.sh to extract manager code
        pre_build_path = os.path.join(src_dir, "scripts", "pre_build_setup.sh")
        if os.path.exists(pre_build_path):
            logger.info(f"Extracting manager code from {pre_build_path}")
            with open(pre_build_path, "r") as f:
                content = f.read()
                # Find the section between 'cat > kometa_ai/state/manager.py << 'EOF'' and the final 'EOF'
                start_marker = "cat > kometa_ai/state/manager.py << 'EOF'"
                end_marker = "EOF"
                if start_marker in content:
                    start_idx = content.find(start_marker) + len(start_marker)
                    end_idx = content.find(end_marker, start_idx)
                    if end_idx > start_idx:
                        state_manager_code = content[start_idx:end_idx].strip()
                        logger.info("Successfully extracted manager code from pre_build_setup.sh")
    
    # If still no manager code, provide minimal implementation
    if not state_manager_code:
        logger.warning("Using minimal manager implementation as fallback")
        state_manager_code = """
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

from kometa_ai.state.models import DecisionRecord

logger = logging.getLogger(__name__)

class StateManager:
    """Manager for persistent state."""
    
    def __init__(self, state_dir: str):
        """Initialize the state manager."""
        self.state_dir = Path(state_dir)
        self.state = {'decisions': {}, 'changes': [], 'errors': []}
        
    def load(self) -> None:
        """Load state from disk."""
        logger.info("Mock StateManager.load() called")
        
    def save(self) -> None:
        """Save state to disk."""
        logger.info("Mock StateManager.save() called")
        
    def get_decision(self, movie_id: int, collection_name: str) -> Optional[DecisionRecord]:
        """Get a decision for a movie/collection pair."""
        return None
        
    def set_decision(self, decision: DecisionRecord) -> None:
        """Set a decision for a movie/collection pair."""
        pass
        
    def get_decisions_for_movie(self, movie_id: int) -> List[DecisionRecord]:
        """Get all decisions for a movie."""
        return []
        
    def log_change(self, *args: Any, **kwargs: Any) -> None:
        """Log a tag change."""
        pass
        
    def log_error(self, *args: Any, **kwargs: Any) -> None:
        """Log an error."""
        pass
        
    def get_changes(self) -> List[Dict[str, Any]]:
        """Get recent changes."""
        return []
        
    def get_errors(self) -> List[Dict[str, Any]]:
        """Get recent errors."""
        return []
        
    def reset(self) -> None:
        """Reset state to empty."""
        pass
        
    def dump(self) -> str:
        """Dump state as formatted JSON string."""
        return "{}"
"""
    
    # Track how many site-packages directories were fixed
    fixed_count = 0
    
    # For each site-packages directory
    for site_pkg in diag_results["site_packages"]:
        try:
            logger.info(f"Fixing state module in {site_pkg}")
            
            # Create kometa_ai directory if it doesn't exist
            kometa_dir = os.path.join(site_pkg, "kometa_ai")
            os.makedirs(kometa_dir, exist_ok=True)
            
            # Ensure kometa_ai/__init__.py exists
            kometa_init = os.path.join(kometa_dir, "__init__.py")
            if not os.path.exists(kometa_init):
                with open(kometa_init, "w") as f:
                    f.write('# kometa-ai package for Claude integration with Radarr.\n')
                logger.info(f"Created {kometa_init}")
            
            # Create py.typed file for the main package
            kometa_py_typed = os.path.join(kometa_dir, "py.typed")
            with open(kometa_py_typed, "w") as f:
                pass  # Empty file
            logger.info(f"Created {kometa_py_typed}")
            
            # Create state directory
            state_dir = os.path.join(kometa_dir, "state")
            os.makedirs(state_dir, exist_ok=True)
            
            # Write state module files using either source files or hardcoded implementations
            
            # 1. __init__.py
            init_content = source_files.get("__init__", {}).get("content", "") if source_files.get("__init__", {}).get("exists", False) else state_init_code
            with open(os.path.join(state_dir, "__init__.py"), "w") as f:
                f.write(init_content)
            logger.info(f"Created/updated {os.path.join(state_dir, '__init__.py')}")
            
            # 2. models.py
            models_content = source_files.get("models", {}).get("content", "") if source_files.get("models", {}).get("exists", False) else state_models_code
            with open(os.path.join(state_dir, "models.py"), "w") as f:
                f.write(models_content)
            logger.info(f"Created/updated {os.path.join(state_dir, 'models.py')}")
            
            # 3. manager.py
            with open(os.path.join(state_dir, "manager.py"), "w") as f:
                f.write(state_manager_code)
            logger.info(f"Created/updated {os.path.join(state_dir, 'manager.py')}")
            
            # Create py.typed for state module
            state_py_typed = os.path.join(state_dir, "py.typed")
            with open(state_py_typed, "w") as f:
                pass  # Empty file
            logger.info(f"Created {state_py_typed}")
            
            # Ensure file permissions are correct
            for py_file in [
                os.path.join(state_dir, "__init__.py"),
                os.path.join(state_dir, "models.py"),
                os.path.join(state_dir, "manager.py"),
                os.path.join(state_dir, "py.typed")
            ]:
                try:
                    # Make sure file is readable by all
                    os.chmod(py_file, 0o644)
                except Exception as e:
                    logger.warning(f"Could not set permissions on {py_file}: {e}")
            
            fixed_count += 1
            logger.info(f"Successfully fixed state module in {site_pkg}")
            
        except Exception as e:
            logger.error(f"Error fixing state module in {site_pkg}: {e}")
    
    return fixed_count > 0


def verify_imports() -> bool:
    """Verify that imports are working properly."""
    logger.info("Verifying imports...")
    # Clear importlib cache to ensure fresh imports
    importlib.invalidate_caches()
    logger.info("Cleared importlib cache")
    
    try:
        # Try to import state module
        logger.info("Testing state module imports...")
        from kometa_ai.state import StateManager, DecisionRecord
        
        logger.info(f"Successfully imported StateManager: {StateManager}")
        logger.info(f"Successfully imported DecisionRecord: {DecisionRecord}")
        
        # Test if we can instantiate StateManager
        try:
            temp_dir = os.path.join(os.getcwd(), "temp_state_test")
            os.makedirs(temp_dir, exist_ok=True)
            
            state_manager = StateManager(temp_dir)
            logger.info(f"Successfully instantiated StateManager: {state_manager}")
            
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Could not clean up test directory {temp_dir}: {e}")
                
        except Exception as e:
            logger.error(f"Failed to instantiate StateManager: {e}")
            return False
        
        # Check module file paths
        state_module = sys.modules.get("kometa_ai.state")
        if state_module and hasattr(state_module, "__file__"):
            logger.info(f"kometa_ai.state module file: {state_module.__file__}")
        else:
            logger.warning("Could not determine kometa_ai.state module file")
        
        manager_module = sys.modules.get("kometa_ai.state.manager")
        if manager_module and hasattr(manager_module, "__file__"):
            logger.info(f"kometa_ai.state.manager module file: {manager_module.__file__}")
        else:
            logger.warning("Could not determine kometa_ai.state.manager module file")
        
        models_module = sys.modules.get("kometa_ai.state.models")
        if models_module and hasattr(models_module, "__file__"):
            logger.info(f"kometa_ai.state.models module file: {models_module.__file__}")
        else:
            logger.warning("Could not determine kometa_ai.state.models module file")
        
        return True
    except ImportError as e:
        logger.error(f"Import verification failed: {e}")
        
        # Provide additional diagnostics
        logger.error("Diagnostic information:")
        
        # Check if kometa_ai is importable
        try:
            import kometa_ai
            logger.info(f"kometa_ai can be imported, version: {getattr(kometa_ai, '__version__', 'unknown')}")
            logger.info(f"kometa_ai location: {getattr(kometa_ai, '__file__', 'unknown')}")
            
            # Check if state module exists
            if hasattr(kometa_ai, 'state'):
                logger.info("kometa_ai.state attribute exists")
                logger.info(f"kometa_ai.state: {kometa_ai.state}")
            else:
                logger.error("kometa_ai.state attribute does not exist")
                
            # List what's in the module
            logger.info(f"kometa_ai contents: {dir(kometa_ai)}")
        except ImportError as e2:
            logger.error(f"Even kometa_ai cannot be imported: {e2}")
        
        return False


def fix_state_module():
    """Fix the state module import issues."""
    logger.info("Starting state module fix...")
    
    # Step 1: Diagnose environment
    diag_results = diagnose_environment()
    
    # Step 2: Fix site-packages installations
    site_fixed = fix_site_packages(diag_results)
    if site_fixed:
        logger.info("Site-packages fix applied")
    else:
        logger.warning("Site-packages fix failed")
    
    # Step 3: Ensure py.typed files exist in all packages
    ensure_py_typed_files(diag_results['cwd'])
    
    # Step 4: Verify imports are working
    imports_working = verify_imports()
    
    if imports_working:
        logger.info("✅ Fix successful: State module imports are working!")
        return True
    else:
        logger.error("❌ Fix failed: State module imports still not working")
        return False


def main():
    """Main function."""
    args = parse_args()
    
    # Set log level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info("Starting CI setup for Kometa-AI...")
    
    run_all = not (args.test_data or args.state_module)
    success = True
    
    # Ensure state directory exists
    state_dir = Path.cwd() / "state"
    if not state_dir.exists():
        state_dir.mkdir(parents=True)
        logger.info(f"Created state directory at {state_dir}")
    
    if run_all or args.state_module:
        logger.info("Running state module fix...")
        state_success = fix_state_module()
        if not state_success:
            success = False
            logger.warning("State module fix completed with warnings/errors")
        else:
            logger.info("State module fix completed successfully")
    
    if run_all or args.test_data:
        logger.info("Creating test data...")
        data_success = create_test_data()
        if not data_success:
            success = False
            logger.warning("Test data creation completed with warnings/errors")
        else:
            logger.info("Test data creation completed successfully")
    
    if success:
        logger.info("✅ CI setup completed successfully!")
        return 0
    else:
        logger.warning("⚠️ CI setup completed with warnings/errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())