import logging
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Set, Optional, Tuple, Any, Generic, TypeVar

from unidecode import unidecode

from kometa_ai.common.models import Tag, MediaItem, T, M

logger = logging.getLogger(__name__)


class BaseTagManager(Generic[T, M], ABC):
    """Abstract base class for tag managers across different media systems."""
    
    TAG_PREFIX = "KAI-"
    
    def __init__(self):
        """Initialize the tag manager."""
        self._tags_cache = {}  # Cache of tag_label -> Tag objects
        self._refresh_tags_cache()
    
    @abstractmethod
    def _refresh_tags_cache(self) -> None:
        """Refresh the internal tags cache.
        
        Must be implemented by subclasses to fetch tags from the specific API.
        """
        pass
    
    @abstractmethod
    def get_tags(self) -> List[T]:
        """Get all tags from the media manager.
        
        Returns:
            List of tags
        """
        pass
    
    @abstractmethod
    def get_tag_by_label(self, label: str) -> Optional[T]:
        """Get a tag by its label.
        
        Args:
            label: Tag label
            
        Returns:
            Tag object or None if not found
        """
        pass
    
    @abstractmethod
    def create_tag(self, label: str) -> T:
        """Create a new tag.
        
        Args:
            label: Tag label
            
        Returns:
            Created tag
        """
        pass
    
    @abstractmethod
    def update_tag(self, tag: T) -> T:
        """Update a tag.
        
        Args:
            tag: Tag object to update
            
        Returns:
            Updated tag
        """
        pass
    
    @abstractmethod
    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag.
        
        Args:
            tag_id: Tag ID
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    def get_all_media(self) -> List[M]:
        """Get all media items.
        
        Returns:
            List of media items
        """
        pass
    
    @abstractmethod
    def get_media_by_id(self, media_id: int) -> M:
        """Get a media item by ID.
        
        Args:
            media_id: Media item ID
            
        Returns:
            Media item
        """
        pass
    
    @abstractmethod
    def add_tag_to_media(self, media_id: int, tag_id: int) -> M:
        """Add a tag to a media item.
        
        Args:
            media_id: Media item ID
            tag_id: Tag ID
            
        Returns:
            Updated media item
        """
        pass
    
    @abstractmethod
    def remove_tag_from_media(self, media_id: int, tag_id: int) -> M:
        """Remove a tag from a media item.
        
        Args:
            media_id: Media item ID
            tag_id: Tag ID
            
        Returns:
            Updated media item
        """
        pass
    
    @abstractmethod
    def update_media_tags(self, media_id: int, tag_ids: List[int]) -> M:
        """Update all tags for a media item.
        
        Args:
            media_id: Media item ID
            tag_ids: List of tag IDs
            
        Returns:
            Updated media item
        """
        pass
    
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
    
    def get_or_create_collection_tag(self, collection_name: str) -> T:
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
        
        # Check if tag exists
        tag = self.get_tag_by_label(tag_label)
        if not tag:
            # Create new tag
            tag = self.create_tag(tag_label)
        
        # Update cache
        self._tags_cache[tag_label.lower()] = tag
        
        return tag
    
    def add_media_to_collection(self, media_id: int, collection_name: str) -> M:
        """Add a media item to a collection by applying the tag.
        
        Args:
            media_id: Media item ID
            collection_name: Collection name
            
        Returns:
            Updated media item
        """
        tag = self.get_or_create_collection_tag(collection_name)
        logger.debug(f"Adding media {media_id} to collection '{collection_name}' with tag {tag.id}")
        
        return self.add_tag_to_media(media_id, tag.id)
    
    def remove_media_from_collection(self, media_id: int, collection_name: str) -> M:
        """Remove a media item from a collection by removing the tag.
        
        Args:
            media_id: Media item ID
            collection_name: Collection name
            
        Returns:
            Updated media item
        """
        tag = self.get_or_create_collection_tag(collection_name)
        logger.debug(f"Removing media {media_id} from collection '{collection_name}' with tag {tag.id}")
        
        return self.remove_tag_from_media(media_id, tag.id)
    
    def get_collection_media(self, collection_name: str) -> List[M]:
        """Get all media items in a collection by tag.
        
        Args:
            collection_name: Collection name
            
        Returns:
            List of media items in the collection
        """
        tag = self.get_or_create_collection_tag(collection_name)
        all_media = self.get_all_media()
        
        return [media for media in all_media if tag.id in media.tag_ids]
    
    def get_media_collections(self, media: M) -> List[str]:
        """Get all collections a media item belongs to.
        
        Args:
            media: Media item
            
        Returns:
            List of collection slugs
        """
        media_tags = set(media.tag_ids)
        collections = []
        
        for tag_label, tag in self._tags_cache.items():
            if tag.id in media_tags and tag_label.lower().startswith(self.TAG_PREFIX.lower()):
                # Extract collection name from tag label
                collection_slug = tag_label[len(self.TAG_PREFIX):].lower()
                collections.append(collection_slug)
        
        return collections
    
    def is_media_in_collection(self, media: M, collection_name: str) -> bool:
        """Check if a media item is in a collection.
        
        Args:
            media: Media item
            collection_name: Collection name
            
        Returns:
            True if the media item is in the collection
        """
        tag = self.get_or_create_collection_tag(collection_name)
        return tag.id in media.tag_ids
    
    def get_ai_managed_tags(self) -> List[T]:
        """Get all tags managed by Kometa-AI (with the KAI- prefix).
        
        Returns:
            List of AI-managed tags
        """
        all_tags = self.get_tags()
        return [tag for tag in all_tags if tag.label.startswith(self.TAG_PREFIX)]
    
    def reconcile_collections(
        self, 
        collection_name: str, 
        media_decisions: Dict[int, bool],
        confidence_threshold: float = 0.7
    ) -> Tuple[List[int], List[int]]:
        """Apply tag changes based on AI decisions.
        
        Args:
            collection_name: Collection name
            media_decisions: Dictionary of media_id -> include decision
            confidence_threshold: Minimum confidence score to apply change
            
        Returns:
            Tuple of (added_media_ids, removed_media_ids)
        """
        logger.info(f"Reconciling collection '{collection_name}' with {len(media_decisions)} decisions")
        
        tag = self.get_or_create_collection_tag(collection_name)
        all_media = {media.id: media for media in self.get_all_media()}
        
        added_media_ids = []
        removed_media_ids = []
        
        for media_id, include in media_decisions.items():
            if media_id not in all_media:
                logger.warning(f"Media ID {media_id} not found, skipping")
                continue
            
            media = all_media[media_id]
            currently_in_collection = tag.id in media.tag_ids
            
            # Add media to collection
            if include and not currently_in_collection:
                logger.debug(f"Adding media {media_id} to collection '{collection_name}'")
                self.add_tag_to_media(media_id, tag.id)
                added_media_ids.append(media_id)
            
            # Remove media from collection
            elif not include and currently_in_collection:
                logger.debug(f"Removing media {media_id} from collection '{collection_name}'")
                self.remove_tag_from_media(media_id, tag.id)
                removed_media_ids.append(media_id)
        
        logger.info(f"Reconciliation complete: added {len(added_media_ids)} items, " 
                    f"removed {len(removed_media_ids)} items")
        
        return added_media_ids, removed_media_ids
    
    def reconcile_media_collections(
        self, 
        media_id: int, 
        collection_decisions: Dict[str, Tuple[bool, float]],
        confidence_threshold: float = 0.7
    ) -> Dict[str, bool]:
        """Apply tag changes for a single media item across multiple collections.
        
        Args:
            media_id: Media item ID
            collection_decisions: Dictionary of collection_name -> (include, confidence) tuples
            confidence_threshold: Minimum confidence score to apply change
            
        Returns:
            Dictionary of collection_name -> changed status
        """
        logger.info(f"Reconciling collections for media {media_id} with {len(collection_decisions)} decisions")
        
        changes = {}
        media = self.get_media_by_id(media_id)
        
        for collection_name, (include, confidence) in collection_decisions.items():
            # Skip if confidence is below threshold
            if confidence < confidence_threshold:
                logger.debug(f"Skipping collection '{collection_name}' due to low confidence: {confidence}")
                changes[collection_name] = False
                continue
            
            tag = self.get_or_create_collection_tag(collection_name)
            currently_in_collection = tag.id in media.tag_ids
            
            # Add media to collection
            if include and not currently_in_collection:
                logger.debug(f"Adding media {media_id} to collection '{collection_name}'")
                self.add_tag_to_media(media_id, tag.id)
                changes[collection_name] = True
            
            # Remove media from collection
            elif not include and currently_in_collection:
                logger.debug(f"Removing media {media_id} from collection '{collection_name}'")
                self.remove_tag_from_media(media_id, tag.id)
                changes[collection_name] = True
            else:
                # No change needed
                changes[collection_name] = False
        
        return changes