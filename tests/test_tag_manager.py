import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag
from kometa_ai.tag_manager import TagManager


@pytest.fixture
def mock_radarr_client():
    """Create a mock RadarrClient."""
    client = Mock(spec=RadarrClient)
    
    # Set up some test tags
    tags = [
        Tag(id=1, label="KAI-action"),
        Tag(id=2, label="KAI-comedy"),
        Tag(id=3, label="KAI-drama"),
        Tag(id=4, label="non-ai-tag")
    ]
    client.get_tags.return_value = tags
    
    # Set up tag lookup by label
    def get_tag_by_label(label):
        for tag in tags:
            if tag.label.lower() == label.lower():
                return tag
        return None
    client.get_tag_by_label.side_effect = get_tag_by_label
    
    # Set up create tag
    def create_tag(label):
        next_id = max(tag.id for tag in tags) + 1
        new_tag = Tag(id=next_id, label=label)
        tags.append(new_tag)
        return new_tag
    client.create_tag.side_effect = create_tag
    
    # Set up get or create tag
    def get_or_create_tag(label):
        tag = get_tag_by_label(label)
        if tag:
            return tag
        return create_tag(label)
    client.get_or_create_tag.side_effect = get_or_create_tag
    
    # Set up some test movies
    movies = [
        Movie(id=101, title="Movie 1", tag_ids=[1, 4]),  # In action
        Movie(id=102, title="Movie 2", tag_ids=[2]),     # In comedy
        Movie(id=103, title="Movie 3", tag_ids=[1, 2]),  # In action and comedy
        Movie(id=104, title="Movie 4", tag_ids=[4]),     # Not in AI collections
        Movie(id=105, title="Movie 5", tag_ids=[])       # No tags
    ]
    client.get_movies.return_value = movies
    
    # Set up get movie by id
    def get_movie(movie_id):
        for movie in movies:
            if movie.id == movie_id:
                return movie
        raise ValueError(f"Movie {movie_id} not found")
    client.get_movie.side_effect = get_movie
    
    # Set up add tag to movie
    def add_tag_to_movie(movie_id, tag_id):
        movie = get_movie(movie_id)
        if tag_id not in movie.tag_ids:
            movie.tag_ids.append(tag_id)
        return movie
    client.add_tag_to_movie.side_effect = add_tag_to_movie
    
    # Set up remove tag from movie
    def remove_tag_from_movie(movie_id, tag_id):
        movie = get_movie(movie_id)
        if tag_id in movie.tag_ids:
            movie.tag_ids.remove(tag_id)
        return movie
    client.remove_tag_from_movie.side_effect = remove_tag_from_movie
    
    # Set up update movie tags
    def update_movie_tags(movie_id, tag_ids):
        movie = get_movie(movie_id)
        movie.tag_ids = tag_ids
        return movie
    client.update_movie_tags.side_effect = update_movie_tags
    
    return client


@pytest.fixture
def tag_manager(mock_radarr_client):
    """Create a TagManager with a mock RadarrClient."""
    return TagManager(mock_radarr_client)


def test_init_refreshes_tags_cache(mock_radarr_client):
    """Test that TagManager initializes and refreshes the tags cache."""
    manager = TagManager(mock_radarr_client)
    assert len(manager._tags_cache) == 4
    mock_radarr_client.get_tags.assert_called_once()
    
    # Verify cache contents
    assert "kai-action" in manager._tags_cache
    assert "kai-comedy" in manager._tags_cache
    assert "kai-drama" in manager._tags_cache
    assert "non-ai-tag" in manager._tags_cache


def test_refresh_tags_cache(tag_manager, mock_radarr_client):
    """Test that _refresh_tags_cache updates the cache."""
    # Add a new tag to the mock
    new_tag = Tag(id=5, label="KAI-new-tag")
    mock_radarr_client.get_tags.return_value.append(new_tag)
    
    # Refresh the cache
    tag_manager._refresh_tags_cache()
    
    # Verify the new tag is in the cache
    assert "kai-new-tag" in tag_manager._tags_cache


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


def test_get_or_create_collection_tag_existing(tag_manager, mock_radarr_client):
    """Test getting an existing collection tag."""
    tag = tag_manager.get_or_create_collection_tag("Action")
    
    assert tag.id == 1
    assert tag.label == "KAI-action"
    # Should use cache, not call API
    mock_radarr_client.get_or_create_tag.assert_not_called()


def test_get_or_create_collection_tag_new(tag_manager, mock_radarr_client):
    """Test creating a new collection tag."""
    tag = tag_manager.get_or_create_collection_tag("New Collection")
    
    assert tag.label == "KAI-new-collection"
    mock_radarr_client.get_or_create_tag.assert_called_once_with("KAI-new-collection")
    
    # Verify it's now in the cache
    assert "kai-new-collection" in tag_manager._tags_cache


def test_add_movie_to_collection(tag_manager, mock_radarr_client):
    """Test adding a movie to a collection."""
    # Add to existing collection
    movie = tag_manager.add_movie_to_collection(105, "Action")
    
    mock_radarr_client.add_tag_to_movie.assert_called_once_with(105, 1)
    assert movie.id == 105
    
    # Add to new collection
    movie = tag_manager.add_movie_to_collection(105, "Thriller")
    
    # Should create the tag first
    mock_radarr_client.get_or_create_tag.assert_called_with("KAI-thriller")


def test_remove_movie_from_collection(tag_manager, mock_radarr_client):
    """Test removing a movie from a collection."""
    movie = tag_manager.remove_movie_from_collection(101, "Action")
    
    mock_radarr_client.remove_tag_from_movie.assert_called_once_with(101, 1)
    assert movie.id == 101


def test_get_collection_movies(tag_manager, mock_radarr_client):
    """Test getting all movies in a collection."""
    movies = tag_manager.get_collection_movies("Action")
    
    assert len(movies) == 2
    assert 101 in [m.id for m in movies]
    assert 103 in [m.id for m in movies]


def test_get_movie_collections(tag_manager):
    """Test getting all collections a movie belongs to."""
    movie = Movie(id=101, title="Test Movie", tag_ids=[1, 3])  # Action and Drama
    collections = tag_manager.get_movie_collections(movie)
    
    assert len(collections) == 2
    assert "action" in collections
    assert "drama" in collections


def test_is_movie_in_collection(tag_manager):
    """Test checking if a movie is in a collection."""
    movie = Movie(id=101, title="Test Movie", tag_ids=[1, 4])
    
    assert tag_manager.is_movie_in_collection(movie, "Action") is True
    assert tag_manager.is_movie_in_collection(movie, "Comedy") is False


def test_get_ai_managed_tags(tag_manager, mock_radarr_client):
    """Test getting all AI-managed tags."""
    ai_tags = tag_manager.get_ai_managed_tags()
    
    assert len(ai_tags) == 3
    assert all(tag.label.startswith("KAI-") for tag in ai_tags)


def test_reconcile_collections(tag_manager, mock_radarr_client):
    """Test reconciling collections based on AI decisions."""
    # Set up test data
    collection_name = "Action"
    movie_decisions = {
        101: True,   # Already in collection, no change
        102: True,   # Add to collection
        103: False,  # Remove from collection
        104: False,  # Not in collection, no change
        999: True    # Non-existent movie, should be skipped
    }
    
    added, removed = tag_manager.reconcile_collections(collection_name, movie_decisions)
    
    assert added == [102]
    assert removed == [103]
    
    # Verify API calls
    mock_radarr_client.add_tag_to_movie.assert_called_with(102, 1)
    mock_radarr_client.remove_tag_from_movie.assert_called_with(103, 1)


def test_reconcile_movie_collections(tag_manager, mock_radarr_client):
    """Test reconciling movie collections with confidence thresholds."""
    movie_id = 105  # Movie with no tags
    collection_decisions = {
        "Action": (True, 0.9),    # High confidence, should add
        "Comedy": (True, 0.6),    # Below threshold, should skip
        "Drama": (False, 0.8)     # Already not in collection, no change
    }
    
    changes = tag_manager.reconcile_movie_collections(movie_id, collection_decisions, confidence_threshold=0.7)
    
    assert changes["Action"] is True
    assert changes["Comedy"] is False
    assert changes["Drama"] is False
    
    # Verify API calls
    mock_radarr_client.add_tag_to_movie.assert_called_once_with(105, 1)
    # Should not try to add to Comedy due to low confidence
    assert not any(call[0][1] == 2 for call in mock_radarr_client.add_tag_to_movie.call_args_list)