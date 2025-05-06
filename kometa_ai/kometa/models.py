from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class CollectionConfig:
    """Configuration for an AI-managed collection."""

    name: str
    slug: str
    enabled: bool = False
    prompt: str = ""
    confidence_threshold: float = 0.7
    priority: int = 0
    exclude_tags: List[str] = field(default_factory=list)
    include_tags: List[str] = field(default_factory=list)
    use_iterative_refinement: bool = False
    refinement_threshold: float = 0.15  # Confidence margin for triggering refinement

    @property
    def tag(self) -> str:
        """Get the Radarr tag for this collection.

        Returns:
            Radarr tag string
        """
        return f"KAI-{self.slug}"

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'CollectionConfig':
        """Create a CollectionConfig from a dictionary.

        Args:
            name: Collection name
            data: Dictionary from parsed YAML

        Returns:
            CollectionConfig object
        """
        from kometa_ai.utils.helpers import slugify

        return cls(
            name=name,
            slug=slugify(name),
            enabled=data.get('enabled', False),
            prompt=data.get('prompt', ''),
            confidence_threshold=float(data.get('confidence_threshold', 0.7)),
            priority=int(data.get('priority', 0)),
            exclude_tags=data.get('exclude_tags', []),
            include_tags=data.get('include_tags', []),
            use_iterative_refinement=data.get('use_iterative_refinement', False),
            refinement_threshold=float(data.get('refinement_threshold', 0.15))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'slug': self.slug,
            'enabled': self.enabled,
            'prompt': self.prompt,
            'confidence_threshold': self.confidence_threshold,
            'priority': self.priority,
            'exclude_tags': self.exclude_tags,
            'include_tags': self.include_tags,
            'use_iterative_refinement': self.use_iterative_refinement,
            'refinement_threshold': self.refinement_threshold
        }
