# mypy: disable-error-code="attr-defined,index,operator,return-value,arg-type"
import os
import json
import logging
import shutil
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union, cast

from kometa_ai.state.models import DecisionRecord

# Use try/except for __version__ to handle CI environment differences
try:
    from kometa_ai.__version__ import __version__
except ImportError:
    __version__ = "0.1.0"  # Fallback version if import fails

logger = logging.getLogger(__name__)


class StateManager:
    """Manager for persistent state."""

    # Current state format version
    STATE_VERSION = 1

    def __init__(self, state_dir: str):
        """Initialize the state manager.

        Args:
            state_dir: Directory for state files
        """
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / 'kometa_state.json'
        self.backup_dir = self.state_dir / 'backups'
        self.state = {
            'version': __version__,
            'state_format_version': self.STATE_VERSION,
            'last_update': datetime.now(UTC).isoformat(),
            'decisions': {},
            'changes': [],
            'errors': []
        }

        # Create directories if they don't exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        """Load state from disk."""
        try:
            if not self.state_file.exists():
                logger.info(f"State file not found at {self.state_file}, using empty state")
                return

            logger.info(f"Loading state from {self.state_file}")
            with open(self.state_file, 'r') as f:
                loaded_state = json.load(f)

            # Validate state format version
            state_version = loaded_state.get('state_format_version', 0)
            if state_version != self.STATE_VERSION:
                logger.warning(
                    f"State format version mismatch: expected {self.STATE_VERSION}, "
                    f"got {state_version}. State migration may be needed."
                )
                # TODO: Implement state migration

            self.state = loaded_state
            logger.info(f"State loaded with {len(self.state.get('decisions', {}))} decisions")
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            self._try_restore_backup()

    def save(self) -> None:
        """Save state to disk."""
        try:
            logger.info(f"Saving state to {self.state_file}")

            # Create a backup first
            if self.state_file.exists():
                self._create_backup()

            # Update timestamp
            self.state['last_update'] = datetime.now(UTC).isoformat()
            self.state['version'] = __version__

            # Ensure directory exists
            self.state_dir.mkdir(parents=True, exist_ok=True)

            # Save state
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)

            logger.info("State saved successfully")
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def _create_backup(self) -> None:
        """Create a backup of the current state file."""
        try:
            timestamp = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
            backup_file = self.backup_dir / f'kometa_state_{timestamp}.json'

            logger.debug(f"Creating state backup at {backup_file}")
            shutil.copy2(self.state_file, backup_file)

            # Keep only the last 5 backups
            backups = sorted(self.backup_dir.glob('kometa_state_*.json'))
            for old_backup in backups[:-5]:
                logger.debug(f"Removing old backup {old_backup}")
                old_backup.unlink()
        except Exception as e:
            logger.error(f"Error creating state backup: {e}")

    def _try_restore_backup(self) -> bool:
        """Try to restore from the latest backup.

        Returns:
            True if restored successfully, False otherwise
        """
        try:
            backups = sorted(self.backup_dir.glob('kometa_state_*.json'))
            if not backups:
                logger.warning("No backups found to restore from")
                return False

            latest_backup = backups[-1]
            logger.warning(f"Attempting to restore from backup {latest_backup}")

            with open(latest_backup, 'r') as f:
                self.state = json.load(f)

            logger.info(f"Successfully restored from backup with {len(self.state.get('decisions', {}))} decisions")
            return True
        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False

    def reset(self) -> None:
        """Reset state to empty."""
        self.state = {
            'version': __version__,
            'state_format_version': self.STATE_VERSION,
            'last_update': datetime.now(UTC).isoformat(),
            'decisions': {},
            'changes': [],
            'errors': []
        }

        logger.info("State reset to empty")
        self.save()

    def get_decision(self, movie_id: int, collection_name: str) -> Optional[DecisionRecord]:
        """Get a decision for a movie/collection pair.

        Args:
            movie_id: Movie ID
            collection_name: Collection name

        Returns:
            Decision record or None if not found
        """
        decisions = self.state.get('decisions', {})
        movie_key = f"movie:{movie_id}"

        if movie_key not in decisions:
            return None

        collections = decisions[movie_key].get('collections', {})
        if collection_name not in collections:
            return None

        decision_data = collections[collection_name]
        decision_data['movie_id'] = movie_id
        decision_data['collection_name'] = collection_name

        return DecisionRecord.from_dict(decision_data)

    def set_decision(self, decision: DecisionRecord) -> None:
        """Set a decision for a movie/collection pair.

        Args:
            decision: Decision record
        """
        decisions = self.state.setdefault('decisions', {})
        movie_key = f"movie:{decision.movie_id}"

        if movie_key not in decisions:
            decisions[movie_key] = {'collections': {}}

        movie_decisions = decisions[movie_key]
        collections = movie_decisions.setdefault('collections', {})

        # Store decision data
        collections[decision.collection_name] = decision.to_dict()

        # Don't store movie_id and collection_name redundantly
        collections[decision.collection_name].pop('movie_id', None)
        collections[decision.collection_name].pop('collection_name', None)

        # Store metadata hash at the movie level if not already there
        movie_decisions['metadata_hash'] = decision.metadata_hash

    def get_decisions_for_movie(self, movie_id: int) -> List[DecisionRecord]:
        """Get all decisions for a movie.

        Args:
            movie_id: Movie ID

        Returns:
            List of decision records
        """
        decisions = self.state.get('decisions', {})
        movie_key = f"movie:{movie_id}"

        if movie_key not in decisions:
            return []

        collections = decisions[movie_key].get('collections', {})
        result = []

        for collection_name, decision_data in collections.items():
            decision_data = decision_data.copy()
            decision_data['movie_id'] = movie_id
            decision_data['collection_name'] = collection_name
            result.append(DecisionRecord.from_dict(decision_data))

        return result

    def get_metadata_hash(self, movie_id: int) -> Optional[str]:
        """Get the stored metadata hash for a movie.

        Args:
            movie_id: Movie ID

        Returns:
            Metadata hash or None if not found
        """
        decisions = self.state.get('decisions', {})
        movie_key = f"movie:{movie_id}"

        if movie_key not in decisions:
            return None

        return decisions[movie_key].get('metadata_hash')

    def log_change(self,
                   movie_id: int,
                   movie_title: str,
                   collection_name: str,
                   action: str,
                   tag: str) -> None:
        """Log a tag change.

        Args:
            movie_id: Movie ID
            movie_title: Movie title
            collection_name: Collection name
            action: Action taken (added/removed)
            tag: Tag affected
        """
        changes = self.state.setdefault('changes', [])

        change = {
            'timestamp': datetime.now(UTC).isoformat(),
            'movie_id': movie_id,
            'title': movie_title,
            'collection': collection_name,
            'action': action,
            'tag': tag
        }

        changes.append(change)

        # Keep only the last 100 changes
        if len(changes) > 100:
            self.state['changes'] = changes[-100:]

    def log_error(self, context: str, error_message: str) -> None:
        """Log an error.

        Args:
            context: Context where the error occurred (collection name, operation, etc.)
            error_message: Error message
        """
        errors = self.state.setdefault('errors', [])

        error = {
            'timestamp': datetime.now(UTC).isoformat(),
            'context': context,
            'message': error_message
        }

        errors.append(error)

        # Keep only the last 50 errors
        if len(errors) > 50:
            self.state['errors'] = errors[-50:]

    def get_changes(self) -> List[Dict[str, Any]]:
        """Get recent changes.

        Returns:
            List of change records
        """
        return self.state.get('changes', [])

    def get_errors(self) -> List[Dict[str, Any]]:
        """Get recent errors.

        Returns:
            List of error records
        """
        return self.state.get('errors', [])

    def clear_errors(self) -> None:
        """Clear all error records."""
        self.state['errors'] = []

    def clear_changes(self) -> None:
        """Clear all change records."""
        self.state['changes'] = []

    def dump(self) -> str:
        """Dump state as formatted JSON string.

        Returns:
            Formatted JSON
        """
        return json.dumps(self.state, indent=2)
        
    def validate_state(self) -> List[str]:
        """Validate the state structure for consistency.
        
        Checks that the state dictionary has the expected keys and structure.
        
        Returns:
            List of validation error messages, empty if valid
        """
        errors = []
        
        # Check required top-level keys
        required_keys = {'version', 'state_format_version', 'last_update', 'decisions', 'changes', 'errors'}
        missing_keys = required_keys - set(self.state.keys())
        if missing_keys:
            errors.append(f"Missing required keys: {', '.join(missing_keys)}")
            
        # Check state_format_version
        if self.state.get('state_format_version') != self.STATE_VERSION:
            errors.append(f"Invalid state_format_version: {self.state.get('state_format_version')} != {self.STATE_VERSION}")
            
        # Check that decisions is a dictionary
        if not isinstance(self.state.get('decisions', {}), dict):
            errors.append("'decisions' is not a dictionary")
            
        # Check that changes is a list
        if not isinstance(self.state.get('changes', []), list):
            errors.append("'changes' is not a list")
            
        # Check that errors is a list
        if not isinstance(self.state.get('errors', []), list):
            errors.append("'errors' is not a list")
            
        # Check decision structure for a sample decision if any exist
        decisions = self.state.get('decisions', {})
        if decisions:
            # Check the first movie entry
            first_movie_key = next(iter(decisions), None)
            if first_movie_key:
                movie_data = decisions[first_movie_key]
                
                # Check that it has a collections key
                if 'collections' not in movie_data:
                    errors.append(f"Movie {first_movie_key} missing 'collections' key")
                elif not isinstance(movie_data['collections'], dict):
                    errors.append(f"Movie {first_movie_key} 'collections' is not a dictionary")
                    
                # Check for metadata_hash
                if 'metadata_hash' not in movie_data:
                    errors.append(f"Movie {first_movie_key} missing 'metadata_hash' key")
                
        return errors
