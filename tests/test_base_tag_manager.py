import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from kometa_ai.common.models import Tag, MediaItem
from kometa_ai.common.tag_manager import BaseTagManager


# Create concrete test implementation of BaseTagManager
class MockTag(Tag):
    pass


class MockMediaItem(MediaItem):
    pass


class MockTagManager(BaseTagManager[MockTag, MockMediaItem]):
    """Concrete implementation of BaseTagManager for testing."""
    
    def __init__(self):
        self.get_tags_mock = Mock(return_value=[])
        self.get_tag_by_label_mock = Mock(return_value=None)
        self.create_tag_mock = Mock()
        self.update_tag_mock = Mock()
        self.delete_tag_mock = Mock(return_value=True)
        self.get_all_media_mock = Mock(return_value=[])
        self.get_media_by_id_mock = Mock()
        self.add_tag_to_media_mock = Mock()
        self.remove_tag_from_media_mock = Mock()
        self.update_media_tags_mock = Mock()
        
        # Skip calling _refresh_tags_cache in __init__
        self._tags_cache = {}
    
    def _refresh_tags_cache(self) -> None:
        tags = self.get_tags()
        self._tags_cache = {tag.label.lower(): tag for tag in tags}
    
    def get_tags(self) -> List[MockTag]:
        return self.get_tags_mock()
    
    def get_tag_by_label(self, label: str) -> Optional[MockTag]:
        return self.get_tag_by_label_mock(label)
    
    def create_tag(self, label: str) -> MockTag:
        return self.create_tag_mock(label)
    
    def update_tag(self, tag: MockTag) -> MockTag:
        return self.update_tag_mock(tag)
    
    def delete_tag(self, tag_id: int) -> bool:
        return self.delete_tag_mock(tag_id)
    
    def get_all_media(self) -> List[MockMediaItem]:
        return self.get_all_media_mock()
    
    def get_media_by_id(self, media_id: int) -> MockMediaItem:
        return self.get_media_by_id_mock(media_id)
    
    def add_tag_to_media(self, media_id: int, tag_id: int) -> MockMediaItem:
        return self.add_tag_to_media_mock(media_id, tag_id)
    
    def remove_tag_from_media(self, media_id: int, tag_id: int) -> MockMediaItem:
        return self.remove_tag_from_media_mock(media_id, tag_id)
    
    def update_media_tags(self, media_id: int, tag_ids: List[int]) -> MockMediaItem:
        return self.update_media_tags_mock(media_id, tag_ids)


@pytest.fixture
def tag_manager():
    """Create a concrete TagManager for testing."""
    return MockTagManager()


def setup_test_data(manager: MockTagManager):
    """Set up test data for the tag manager."""
    # Create test tags
    test_tags = [
        MockTag(id=1, label="KAI-action"),
        MockTag(id=2, label="KAI-comedy"),
        MockTag(id=3, label="KAI-drama"),
        MockTag(id=4, label="non-ai-tag")
    ]
    
    # Create test media items
    test_media = [
        MockMediaItem(id=101, title="Item 1", tag_ids=[1, 4]),  # In action
        MockMediaItem(id=102, title="Item 2", tag_ids=[2]),     # In comedy
        MockMediaItem(id=103, title="Item 3", tag_ids=[1, 2]),  # In action and comedy
        MockMediaItem(id=104, title="Item 4", tag_ids=[4]),     # Not in AI collections
        MockMediaItem(id=105, title="Item 5", tag_ids=[])       # No tags
    ]
    
    # Configure mocks
    manager.get_tags_mock.return_value = test_tags
    manager.get_all_media_mock.return_value = test_media
    
    # Set up get_tag_by_label mock
    def get_tag_by_label(label):
        for tag in test_tags:
            if tag.label.lower() == label.lower():
                return tag
        return None
    manager.get_tag_by_label_mock.side_effect = get_tag_by_label
    
    # Set up create_tag mock
    def create_tag(label):
        next_id = max(tag.id for tag in test_tags) + 1
        new_tag = MockTag(id=next_id, label=label)
        test_tags.append(new_tag)
        return new_tag
    manager.create_tag_mock.side_effect = create_tag
    
    # Set up get_media_by_id mock
    def get_media_by_id(media_id):
        for media in test_media:
            if media.id == media_id:
                return media
        raise ValueError(f"Media {media_id} not found")
    manager.get_media_by_id_mock.side_effect = get_media_by_id
    
    # Set up add_tag_to_media mock
    def add_tag_to_media(media_id, tag_id):
        media = get_media_by_id(media_id)
        if tag_id not in media.tag_ids:
            media.tag_ids.append(tag_id)
        return media
    manager.add_tag_to_media_mock.side_effect = add_tag_to_media
    
    # Set up remove_tag_from_media mock
    def remove_tag_from_media(media_id, tag_id):
        media = get_media_by_id(media_id)
        if tag_id in media.tag_ids:
            media.tag_ids.remove(tag_id)
        return media
    manager.remove_tag_from_media_mock.side_effect = remove_tag_from_media
    
    # Refresh cache
    manager._refresh_tags_cache()
    
    return test_tags, test_media


def test_slugify_collection_name(tag_manager):
    """Test slugification of collection names."""
    assert tag_manager.slugify_collection_name("Action Movies") == "action-movies"
    assert tag_manager.slugify_collection_name("Sci-Fi & Fantasy") == "sci-fi-fantasy"
    assert tag_manager.slugify_collection_name("Film Noir (1940s)") == "film-noir-1940s"
    assert tag_manager.slugify_collection_name("Año Nuevo") == "ano-nuevo"
    assert tag_manager.slugify_collection_name(" Trim Spaces ") == "trim-spaces"
    assert tag_manager.slugify_collection_name("___Special___Chars___") == "special-chars"


def test_get_tag_label_for_collection(tag_manager):
    """Test generating tag labels for collections."""
    assert tag_manager.get_tag_label_for_collection("Action") == "KAI-action"
    assert tag_manager.get_tag_label_for_collection("Sci-Fi Movies") == "KAI-sci-fi-movies"


def test_get_or_create_collection_tag(tag_manager):
    """Test getting or creating a collection tag."""
    # Set up test data
    test_tags, _ = setup_test_data(tag_manager)
    
    # Test getting existing tag
    tag = tag_manager.get_or_create_collection_tag("Action")
    assert tag.id == 1
    assert tag.label == "KAI-action"
    
    # Test creating new tag
    tag_manager.get_tag_by_label_mock.return_value = None
    new_tag = MockTag(id=5, label="KAI-new-collection")
    tag_manager.create_tag_mock.return_value = new_tag
    
    tag = tag_manager.get_or_create_collection_tag("New Collection")
    assert tag.id == 5
    assert tag.label == "KAI-new-collection"
    tag_manager.create_tag_mock.assert_called_with("KAI-new-collection")


def test_get_ai_managed_tags(tag_manager):
    """Test getting AI-managed tags."""
    # Set up test data
    test_tags, _ = setup_test_data(tag_manager)
    
    ai_tags = tag_manager.get_ai_managed_tags()
    assert len(ai_tags) == 3
    assert all(tag.label.startswith("KAI-") for tag in ai_tags)


def test_add_media_to_collection(tag_manager):
    """Test adding media to a collection."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    # Test adding to existing collection
    tag_manager.add_media_to_collection(105, "Action")
    tag_manager.add_tag_to_media_mock.assert_called_with(105, 1)
    
    # Test adding to new collection
    tag_manager.get_tag_by_label_mock.return_value = None
    new_tag = MockTag(id=5, label="KAI-thriller")
    tag_manager.create_tag_mock.return_value = new_tag
    
    tag_manager.add_media_to_collection(105, "Thriller")
    tag_manager.create_tag_mock.assert_called_with("KAI-thriller")
    tag_manager.add_tag_to_media_mock.assert_called_with(105, 5)


def test_remove_media_from_collection(tag_manager):
    """Test removing media from a collection."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    tag_manager.remove_media_from_collection(101, "Action")
    tag_manager.remove_tag_from_media_mock.assert_called_with(101, 1)


def test_get_collection_media(tag_manager):
    """Test getting media in a collection."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    media_items = tag_manager.get_collection_media("Action")
    assert len(media_items) == 2
    assert 101 in [m.id for m in media_items]
    assert 103 in [m.id for m in media_items]


def test_get_media_collections(tag_manager):
    """Test getting collections a media item belongs to."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    # Test media in multiple collections
    collections = tag_manager.get_media_collections(test_media[2])  # Item 3, in action and comedy
    assert len(collections) == 2
    assert "action" in collections
    assert "comedy" in collections
    
    # Test media not in any AI collections
    collections = tag_manager.get_media_collections(test_media[3])  # Item 4, only non-AI tag
    assert len(collections) == 0


def test_is_media_in_collection(tag_manager):
    """Test checking if media is in a collection."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    assert tag_manager.is_media_in_collection(test_media[0], "Action") is True
    assert tag_manager.is_media_in_collection(test_media[0], "Comedy") is False


def test_reconcile_collections(tag_manager):
    """Test reconciling collections based on AI decisions."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    # Set up test decisions
    collection_name = "Action"
    media_decisions = {
        101: True,   # Already in collection, no change
        102: True,   # Add to collection
        103: False,  # Remove from collection
        104: False,  # Not in collection, no change
        999: True    # Non-existent media, should be skipped
    }
    
    # Configure get_media_by_id to raise for invalid ID
    def get_media_by_id(media_id):
        if media_id == 999:
            raise ValueError("Media not found")
        return next((m for m in test_media if m.id == media_id), None)
    tag_manager.get_media_by_id_mock.side_effect = get_media_by_id
    
    added, removed = tag_manager.reconcile_collections(collection_name, media_decisions)
    
    assert 102 in added
    assert 103 in removed
    assert len(added) == 1
    assert len(removed) == 1


def test_reconcile_media_collections(tag_manager):
    """Test reconciling a media item's collections with confidence thresholds."""
    # Set up test data
    test_tags, test_media = setup_test_data(tag_manager)
    
    # Set up test decisions with confidence values
    media_id = 105  # Item 5, no tags
    collection_decisions = {
        "Action": (True, 0.9),    # High confidence, should add
        "Comedy": (True, 0.6),    # Below threshold, should skip
        "Drama": (False, 0.8)     # Already not in collection, no change
    }
    
    changes = tag_manager.reconcile_media_collections(media_id, collection_decisions, confidence_threshold=0.7)
    
    assert changes["Action"] is True
    assert changes["Comedy"] is False
    assert changes["Drama"] is False
    
    # Verify correct method calls
    tag_manager.add_tag_to_media_mock.assert_called_once_with(105, 1)
    assert tag_manager.remove_tag_from_media_mock.call_count == 0