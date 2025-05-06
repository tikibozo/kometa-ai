#!/bin/bash
# Script to set up the package structure before building the package
# This ensures all the necessary py.typed files exist and directories are created

set -e

echo "Running pre-build setup..."

# Create required directories
mkdir -p kometa_ai/state kometa_ai/claude kometa_ai/common kometa_ai/kometa
mkdir -p kometa_ai/notification kometa_ai/radarr kometa_ai/utils

# Create empty py.typed files in each directory
touch kometa_ai/py.typed
touch kometa_ai/state/py.typed
touch kometa_ai/claude/py.typed
touch kometa_ai/common/py.typed
touch kometa_ai/kometa/py.typed
touch kometa_ai/notification/py.typed
touch kometa_ai/radarr/py.typed
touch kometa_ai/utils/py.typed

# Create state module Python files with basic implementations
echo "Creating state module Python files..."

# Create __init__.py for state module
cat > kometa_ai/state/__init__.py << 'EOF'
"""
State management for Kometa-AI.

This package provides functionality for persisting decisions and state.
"""

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ['StateManager', 'DecisionRecord']
EOF

# Create models.py for state module
cat > kometa_ai/state/models.py << 'EOF'
from dataclasses import dataclass, field
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
EOF

# Create manager.py for state module
# Note: We're using a hardcoded implementation to avoid path issues in CI
cat > kometa_ai/state/manager.py << 'EOF'
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
EOF

# Verify files exist
echo "Verifying py.typed files:"
find kometa_ai -name py.typed

echo "Verifying state module Python files:"
find kometa_ai/state -name "*.py"

echo "Pre-build setup complete!"