import logging
from typing import List, Dict, Optional, Any, cast

from kometa_ai.common.models import Tag as BaseTag, MediaItem as BaseMediaItem
from kometa_ai.common.tag_manager import BaseTagManager
from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag

logger = logging.getLogger(__name__)


class RadarrTagManager(BaseTagManager[Tag, Movie]):
    """Tag manager implementation for Radarr."""

    def __init__(self, radarr_client: RadarrClient):
        """Initialize the Radarr tag manager.

        Args:
            radarr_client: RadarrClient instance for API operations
        """
        self.radarr = radarr_client
        super().__init__()

    def _refresh_tags_cache(self) -> None:
        """Refresh the internal tags cache."""
        tags = self.radarr.get_tags()
        self._tags_cache = {tag.label.lower(): tag for tag in tags}

    def get_tags(self) -> List[Tag]:
        """Get all tags from Radarr.

        Returns:
            List of tags
        """
        return self.radarr.get_tags()

    def get_tag_by_label(self, label: str) -> Optional[Tag]:
        """Get a tag by its label.

        Args:
            label: Tag label

        Returns:
            Tag object or None if not found
        """
        return self.radarr.get_tag_by_label(label)

    def create_tag(self, label: str) -> Tag:
        """Create a new tag in Radarr.

        Args:
            label: Tag label

        Returns:
            Created tag
        """
        return self.radarr.create_tag(label)

    def update_tag(self, tag: Tag) -> Tag:
        """Update a tag in Radarr.

        Args:
            tag: Tag object to update

        Returns:
            Updated tag
        """
        return self.radarr.update_tag(tag)

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag from Radarr.

        Args:
            tag_id: Tag ID

        Returns:
            True if successful
        """
        return self.radarr.delete_tag(tag_id)

    def get_all_media(self) -> List[Movie]:
        """Get all movies from Radarr.

        Returns:
            List of movies
        """
        return self.radarr.get_movies()

    def get_media_by_id(self, media_id: int) -> Movie:
        """Get a movie by ID.

        Args:
            media_id: Movie ID

        Returns:
            Movie object
        """
        return self.radarr.get_movie(media_id)

    def add_tag_to_media(self, media_id: int, tag_id: int) -> Movie:
        """Add a tag to a movie.

        Args:
            media_id: Movie ID
            tag_id: Tag ID

        Returns:
            Updated movie
        """
        return self.radarr.add_tag_to_movie(media_id, tag_id)

    def remove_tag_from_media(self, media_id: int, tag_id: int) -> Movie:
        """Remove a tag from a movie.

        Args:
            media_id: Movie ID
            tag_id: Tag ID

        Returns:
            Updated movie
        """
        return self.radarr.remove_tag_from_movie(media_id, tag_id)

    def update_media_tags(self, media_id: int, tag_ids: List[int]) -> Movie:
        """Update all tags for a movie.

        Args:
            media_id: Movie ID
            tag_ids: List of tag IDs

        Returns:
            Updated movie
        """
        return self.radarr.update_movie_tags(media_id, tag_ids)
