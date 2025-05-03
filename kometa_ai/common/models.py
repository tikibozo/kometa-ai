from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, TypeVar, Generic

@dataclass
class Tag:
    """Generic tag model for media managers."""

    id: int
    label: str


@dataclass
class MediaItem:
    """Base class for media items (movies, series, etc.)."""

    id: int
    title: str
    tag_ids: List[int] = field(default_factory=list)

    @property
    def has_tags(self) -> bool:
        """Check if the media item has any tags."""
        return len(self.tag_ids) > 0

    def has_tag(self, tag_id: int) -> bool:
        """Check if the media item has a specific tag."""
        return tag_id in self.tag_ids

    def add_tag(self, tag_id: int) -> None:
        """Add a tag to the media item."""
        if tag_id not in self.tag_ids:
            self.tag_ids.append(tag_id)

    def remove_tag(self, tag_id: int) -> None:
        """Remove a tag from the media item."""
        if tag_id in self.tag_ids:
            self.tag_ids.remove(tag_id)


# Type variables for generic typing
T = TypeVar('T', bound=Tag)
M = TypeVar('M', bound=MediaItem)
