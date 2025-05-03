import logging
import re
from typing import List, Dict, Set, Optional, Tuple, Any

from unidecode import unidecode

from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag

logger = logging.getLogger(__name__)


class TagManager:
    """Manager for handling all tag-related operations."""

    TAG_PREFIX = "KAI-"

    def __init__(self, radarr_client: RadarrClient):
        """Initialize the tag manager.

        Args:
            radarr_client: RadarrClient instance for API operations
        """
        self.radarr = radarr_client
        self._tags_cache: Dict[str, Tag] = {}  # Cache of tag_label -> Tag objects
        self._refresh_tags_cache()

    def _refresh_tags_cache(self) -> None:
        """Refresh the internal tags cache."""
        tags = self.radarr.get_tags()
        self._tags_cache = {tag.label.lower(): tag for tag in tags}

    def slugify_collection_name(self, collection_name: str) -> str:
        """Convert a collection name to a slug format.

        Args:
            collection_name: Collection name to slugify

        Returns:
            Slugified collection name
        """
        # Convert to ASCII
        name = unidecode(collection_name)
        # Convert to lowercase
        name = name.lower()
        # Replace spaces and special chars with hyphens
        name = re.sub(r'[^a-z0-9]+', '-', name)
        # Remove leading/trailing hyphens
        name = name.strip('-')

        return name

    def get_tag_label_for_collection(self, collection_name: str) -> str:
        """Get the tag label for a collection.

        Args:
            collection_name: Collection name

        Returns:
            Tag label with prefix
        """
        slug = self.slugify_collection_name(collection_name)
        return f"{self.TAG_PREFIX}{slug}"

    def get_or_create_collection_tag(self, collection_name: str) -> Tag:
        """Get or create a tag for a collection.

        Args:
            collection_name: Collection name

        Returns:
            Tag object
        """
        tag_label = self.get_tag_label_for_collection(collection_name)

        # Check cache first
        cached_tag = self._tags_cache.get(tag_label.lower())
        if cached_tag:
            return cached_tag

        # Get or create the tag via API
        tag = self.radarr.get_or_create_tag(tag_label)

        # Update cache
        self._tags_cache[tag_label.lower()] = tag

        return tag

    def add_movie_to_collection(self, movie_id: int, collection_name: str) -> Movie:
        """Add a movie to a collection by applying the tag.

        Args:
            movie_id: Movie ID
            collection_name: Collection name

        Returns:
            Updated movie object
        """
        tag = self.get_or_create_collection_tag(collection_name)
        logger.debug(f"Adding movie {movie_id} to collection '{collection_name}' with tag {tag.id}")

        return self.radarr.add_tag_to_movie(movie_id, tag.id)

    def remove_movie_from_collection(self, movie_id: int, collection_name: str) -> Movie:
        """Remove a movie from a collection by removing the tag.

        Args:
            movie_id: Movie ID
            collection_name: Collection name

        Returns:
            Updated movie object
        """
        tag = self.get_or_create_collection_tag(collection_name)
        logger.debug(f"Removing movie {movie_id} from collection '{collection_name}' with tag {tag.id}")

        return self.radarr.remove_tag_from_movie(movie_id, tag.id)

    def get_collection_movies(self, collection_name: str) -> List[Movie]:
        """Get all movies in a collection by tag.

        Args:
            collection_name: Collection name

        Returns:
            List of movies in the collection
        """
        tag = self.get_or_create_collection_tag(collection_name)
        all_movies = self.radarr.get_movies()

        return [movie for movie in all_movies if tag.id in movie.tag_ids]

    def get_movie_collections(self, movie: Movie) -> List[str]:
        """Get all collections a movie belongs to.

        Args:
            movie: Movie object

        Returns:
            List of collection names
        """
        movie_tags = set(movie.tag_ids)
        collections = []

        for tag_label, tag in self._tags_cache.items():
            if tag.id in movie_tags and tag_label.lower().startswith(self.TAG_PREFIX.lower()):
                # Extract collection name from tag label
                collection_slug = tag_label[len(self.TAG_PREFIX):].lower()
                collections.append(collection_slug)

        return collections

    def is_movie_in_collection(self, movie: Movie, collection_name: str) -> bool:
        """Check if a movie is in a collection.

        Args:
            movie: Movie object
            collection_name: Collection name

        Returns:
            True if the movie is in the collection
        """
        tag = self.get_or_create_collection_tag(collection_name)
        return tag.id in movie.tag_ids

    def get_ai_managed_tags(self) -> List[Tag]:
        """Get all tags managed by Kometa-AI (with the KAI- prefix).

        Returns:
            List of AI-managed tags
        """
        all_tags = self.radarr.get_tags()
        return [tag for tag in all_tags if tag.label.startswith(self.TAG_PREFIX)]

    def reconcile_collections(
        self,
        collection_name: str,
        movie_decisions: Dict[int, bool],
        confidence_threshold: float = 0.7
    ) -> Tuple[List[int], List[int]]:
        """Apply tag changes based on AI decisions.

        Args:
            collection_name: Collection name
            movie_decisions: Dictionary of movie_id -> include decision
            confidence_threshold: Minimum confidence score to apply change

        Returns:
            Tuple of (added_movie_ids, removed_movie_ids)
        """
        logger.info(f"Reconciling collection '{collection_name}' with {len(movie_decisions)} decisions")

        tag = self.get_or_create_collection_tag(collection_name)
        all_movies = {movie.id: movie for movie in self.radarr.get_movies()}

        added_movie_ids = []
        removed_movie_ids = []

        for movie_id, include in movie_decisions.items():
            if movie_id not in all_movies:
                logger.warning(f"Movie ID {movie_id} not found in Radarr, skipping")
                continue

            movie = all_movies[movie_id]
            currently_in_collection = tag.id in movie.tag_ids

            # Add movie to collection
            if include and not currently_in_collection:
                logger.debug(f"Adding movie {movie_id} to collection '{collection_name}'")
                self.radarr.add_tag_to_movie(movie_id, tag.id)
                added_movie_ids.append(movie_id)

            # Remove movie from collection
            elif not include and currently_in_collection:
                logger.debug(f"Removing movie {movie_id} from collection '{collection_name}'")
                self.radarr.remove_tag_from_movie(movie_id, tag.id)
                removed_movie_ids.append(movie_id)

        logger.info(f"Reconciliation complete: added {len(added_movie_ids)} movies, "
                    f"removed {len(removed_movie_ids)} movies")

        return added_movie_ids, removed_movie_ids

    def reconcile_movie_collections(
        self,
        movie_id: int,
        collection_decisions: Dict[str, Tuple[bool, float]],
        confidence_threshold: float = 0.7
    ) -> Dict[str, bool]:
        """Apply tag changes for a single movie across multiple collections.

        Args:
            movie_id: Movie ID
            collection_decisions: Dictionary of collection_name -> (include, confidence) tuples
            confidence_threshold: Minimum confidence score to apply change

        Returns:
            Dictionary of collection_name -> changed status
        """
        logger.info(f"Reconciling collections for movie {movie_id} with {len(collection_decisions)} decisions")

        changes = {}
        movie = self.radarr.get_movie(movie_id)

        for collection_name, (include, confidence) in collection_decisions.items():
            # Skip if confidence is below threshold
            if confidence < confidence_threshold:
                logger.debug(f"Skipping collection '{collection_name}' for movie {movie_id} due to low confidence: {confidence}")
                changes[collection_name] = False
                continue

            tag = self.get_or_create_collection_tag(collection_name)
            currently_in_collection = tag.id in movie.tag_ids

            # Add movie to collection
            if include and not currently_in_collection:
                logger.debug(f"Adding movie {movie_id} to collection '{collection_name}'")
                self.radarr.add_tag_to_movie(movie_id, tag.id)
                changes[collection_name] = True

            # Remove movie from collection
            elif not include and currently_in_collection:
                logger.debug(f"Removing movie {movie_id} from collection '{collection_name}'")
                self.radarr.remove_tag_from_movie(movie_id, tag.id)
                changes[collection_name] = True
            else:
                # No change needed
                changes[collection_name] = False

        return changes

    def reconcile_collection_membership(
        self,
        collection_name: str,
        tag: str,
        included_movie_ids: List[int],
        all_movies: List[Movie]
    ) -> List[Dict[str, Any]]:
        """Apply tag changes based on which movies should be included in a collection.

        Args:
            collection_name: Name of the collection
            tag: Tag string for the collection (e.g., "KAI-action-movies")
            included_movie_ids: List of movie IDs that should be in the collection
            all_movies: List of all movies from Radarr

        Returns:
            List of change dictionaries with movie_id, action, etc.
        """
        logger.info(f"Reconciling collection membership for '{collection_name}' with tag {tag}")

        # Get the tag object
        tag_obj = self.radarr.get_or_create_tag(tag)
        tag_id = tag_obj.id

        # Find which movies are currently in the collection
        current_movie_ids = {movie.id for movie in all_movies if tag_id in movie.tag_ids}

        # Convert included_movie_ids to a set for comparison
        included_movie_ids_set = set(included_movie_ids)

        # Calculate additions and removals
        to_add = included_movie_ids_set - current_movie_ids
        to_remove = current_movie_ids - included_movie_ids_set

        changes = []

        # Add movies to the collection
        for movie_id in to_add:
            logger.debug(f"Adding movie {movie_id} to collection '{collection_name}'")
            self.radarr.add_tag_to_movie(movie_id, tag_id)
            changes.append({
                "movie_id": movie_id,
                "collection": collection_name,
                "action": "added",
                "tag": tag
            })

        # Remove movies from the collection
        for movie_id in to_remove:
            logger.debug(f"Removing movie {movie_id} from collection '{collection_name}'")
            self.radarr.remove_tag_from_movie(movie_id, tag_id)
            changes.append({
                "movie_id": movie_id,
                "collection": collection_name,
                "action": "removed",
                "tag": tag
            })

        logger.info(f"Reconciliation complete: added {len(to_add)} movies, removed {len(to_remove)} movies")
        return changes
