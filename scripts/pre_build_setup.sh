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

# Create manager.py for state module by copying the template
cp ../templates/state_manager_template.py kometa_ai/state/manager.py

# Verify files exist
echo "Verifying py.typed files:"
find kometa_ai -name py.typed

echo "Verifying state module Python files:"
find kometa_ai/state -name "*.py"

echo "Pre-build setup complete!"