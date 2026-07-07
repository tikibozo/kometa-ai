import logging
from typing import List, Dict, Any, Optional

from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie

logger = logging.getLogger(__name__)


class TagManager:
    """Applies collection membership decisions as Radarr tags."""

    TAG_PREFIX = "KAI-"

    def __init__(self, radarr_client: RadarrClient):
        """Initialize the tag manager.

        Args:
            radarr_client: RadarrClient instance for API operations
        """
        self.radarr = radarr_client

    def reconcile_collection_membership(
        self,
        collection_name: str,
        tag: str,
        included_movie_ids: List[int],
        all_movies: Optional[List[Movie]] = None
    ) -> List[Dict[str, Any]]:
        """Apply tag changes based on which movies should be included in a collection.

        Args:
            collection_name: Name of the collection
            tag: Tag string for the collection (e.g., "KAI-action-movies")
            included_movie_ids: List of movie IDs that should be in the collection
            all_movies: Optional pre-fetched movie list to diff against. When
                omitted (the default, and what the pipeline now does), current
                tag membership is refetched from Radarr immediately before the
                diff.

        Returns:
            List of change dictionaries with movie_id, action, etc.
        """
        logger.info(f"Reconciling collection membership for '{collection_name}' with tag {tag}")

        tag_obj = self.radarr.get_or_create_tag(tag)
        tag_id = tag_obj.id

        # Refetch current tag membership immediately before diffing. The run's
        # start-of-run snapshot can be stale by the time we reconcile — a long
        # classification pass, or a second kometa-ai run mutating tags in
        # parallel, means diffing against that snapshot re-adds or re-removes
        # tags to match day-one state (the concurrent-run clobber bug). A fresh
        # read (paired with the pipeline run-lock) makes the diff reflect
        # reality at write time. Callers may still pass an explicit snapshot.
        if all_movies is None:
            all_movies = self.radarr.get_movies()

        current_movie_ids = {movie.id for movie in all_movies if tag_id in movie.tag_ids}
        included_movie_ids_set = set(included_movie_ids)

        to_add = included_movie_ids_set - current_movie_ids
        to_remove = current_movie_ids - included_movie_ids_set

        changes = []

        for movie_id in to_add:
            logger.debug(f"Adding movie {movie_id} to collection '{collection_name}'")
            self.radarr.add_tag_to_movie(movie_id, tag_id)
            changes.append({
                "movie_id": movie_id,
                "collection": collection_name,
                "action": "added",
                "tag": tag
            })

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
