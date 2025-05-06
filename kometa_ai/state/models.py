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
