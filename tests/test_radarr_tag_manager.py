import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag
from kometa_ai.radarr.tag_manager import RadarrTagManager


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
    
    # Set up some test movies
    movies = [
        Movie(id=101, title="Movie 1", tag_ids=[1, 4]),  # In action
        Movie(id=102, title="Movie 2", tag_ids=[2]),     # In comedy
        Movie(id=103, title="Movie 3", tag_ids=[1, 2]),  # In action and comedy
        Movie(id=104, title="Movie 4", tag_ids=[4]),     # Not in AI collections
        Movie(id=105, title="Movie 5", tag_ids=[])       # No tags
    ]
    
    # Configure client methods
    client.get_tags.return_value = tags
    client.get_movies.return_value = movies
    
    # Set up get_tag_by_label
    def get_tag_by_label(label):
        for tag in tags:
            if tag.label.lower() == label.lower():
                return tag
        return None
    client.get_tag_by_label.side_effect = get_tag_by_label
    
    # Set up create_tag
    def create_tag(label):
        next_id = max(tag.id for tag in tags) + 1
        new_tag = Tag(id=next_id, label=label)
        tags.append(new_tag)
        return new_tag
    client.create_tag.side_effect = create_tag
    
    # Set up get_movie
    def get_movie(movie_id):
        for movie in movies:
            if movie.id == movie_id:
                return movie
        raise ValueError(f"Movie {movie_id} not found")
    client.get_movie.side_effect = get_movie
    
    # Set up add_tag_to_movie
    def add_tag_to_movie(movie_id, tag_id):
        movie = get_movie(movie_id)
        if tag_id not in movie.tag_ids:
            movie.tag_ids.append(tag_id)
        return movie
    client.add_tag_to_movie.side_effect = add_tag_to_movie
    
    # Set up remove_tag_from_movie
    def remove_tag_from_movie(movie_id, tag_id):
        movie = get_movie(movie_id)
        if tag_id in movie.tag_ids:
            movie.tag_ids.remove(tag_id)
        return movie
    client.remove_tag_from_movie.side_effect = remove_tag_from_movie
    
    # Set up update_movie_tags
    def update_movie_tags(movie_id, tag_ids):
        movie = get_movie(movie_id)
        movie.tag_ids = list(tag_ids)
        return movie
    client.update_movie_tags.side_effect = update_movie_tags
    
    # Set up update_tag
    def update_tag(tag):
        for i, existing_tag in enumerate(tags):
            if existing_tag.id == tag.id:
                tags[i] = tag
                return tag
        return tag
    client.update_tag.side_effect = update_tag
    
    # Set up delete_tag
    def delete_tag(tag_id):
        for i, tag in enumerate(tags):
            if tag.id == tag_id:
                del tags[i]
                return True
        return False
    client.delete_tag.side_effect = delete_tag
    
    return client


@pytest.fixture
def tag_manager(mock_radarr_client):
    """Create a RadarrTagManager with a mock RadarrClient."""
    return RadarrTagManager(mock_radarr_client)


def test_init_and_refresh_tags_cache(mock_radarr_client):
    """Test that RadarrTagManager initializes and refreshes the tags cache."""
    manager = RadarrTagManager(mock_radarr_client)
    
    mock_radarr_client.get_tags.assert_called_once()
    assert len(manager._tags_cache) == 4
    
    # Verify the cache is built correctly
    assert "kai-action" in manager._tags_cache
    assert "kai-comedy" in manager._tags_cache
    assert "kai-drama" in manager._tags_cache
    assert "non-ai-tag" in manager._tags_cache


def test_get_tags(tag_manager, mock_radarr_client):
    """Test get_tags delegates to RadarrClient."""
    # Reset the mock because it was already called during initialization
    mock_radarr_client.get_tags.reset_mock()
    tag_manager.get_tags()
    mock_radarr_client.get_tags.assert_called_once()


def test_get_tag_by_label(tag_manager, mock_radarr_client):
    """Test get_tag_by_label delegates to RadarrClient."""
    tag_manager.get_tag_by_label("test")
    mock_radarr_client.get_tag_by_label.assert_called_once_with("test")


def test_create_tag(tag_manager, mock_radarr_client):
    """Test create_tag delegates to RadarrClient."""
    tag_manager.create_tag("test")
    mock_radarr_client.create_tag.assert_called_once_with("test")


def test_update_tag(tag_manager, mock_radarr_client):
    """Test update_tag delegates to RadarrClient."""
    tag = Tag(id=1, label="test")
    tag_manager.update_tag(tag)
    mock_radarr_client.update_tag.assert_called_once_with(tag)


def test_delete_tag(tag_manager, mock_radarr_client):
    """Test delete_tag delegates to RadarrClient."""
    tag_manager.delete_tag(1)
    mock_radarr_client.delete_tag.assert_called_once_with(1)


def test_get_all_media(tag_manager, mock_radarr_client):
    """Test get_all_media delegates to get_movies."""
    tag_manager.get_all_media()
    mock_radarr_client.get_movies.assert_called_once()


def test_get_media_by_id(tag_manager, mock_radarr_client):
    """Test get_media_by_id delegates to get_movie."""
    tag_manager.get_media_by_id(101)
    mock_radarr_client.get_movie.assert_called_once_with(101)


def test_add_tag_to_media(tag_manager, mock_radarr_client):
    """Test add_tag_to_media delegates to add_tag_to_movie."""
    tag_manager.add_tag_to_media(101, 2)
    mock_radarr_client.add_tag_to_movie.assert_called_once_with(101, 2)


def test_remove_tag_from_media(tag_manager, mock_radarr_client):
    """Test remove_tag_from_media delegates to remove_tag_from_movie."""
    tag_manager.remove_tag_from_media(101, 1)
    mock_radarr_client.remove_tag_from_movie.assert_called_once_with(101, 1)


def test_update_media_tags(tag_manager, mock_radarr_client):
    """Test update_media_tags delegates to update_movie_tags."""
    tag_manager.update_media_tags(101, [2, 3])
    mock_radarr_client.update_movie_tags.assert_called_once_with(101, [2, 3])


def test_integration_with_base_class(tag_manager, mock_radarr_client):
    """Test that RadarrTagManager integrates with the base class functionality."""
    # Set up a fresh mock for better test isolation
    mock_radarr_client.reset_mock()
    
    # Create a predictable state for the test
    movies = [
        Movie(id=101, title="Movie 1", tag_ids=[1, 4]),
        Movie(id=102, title="Movie 2", tag_ids=[2]),
        Movie(id=105, title="Movie 5", tag_ids=[])
    ]
    mock_radarr_client.get_movies.return_value = movies
    
    # Test a method from the base class that relies on the concrete implementation
    tag_manager.add_media_to_collection(105, "Action")
    
    # Verify the correct delegations occurred
    mock_radarr_client.add_tag_to_movie.assert_called_with(105, 1)
    
    # Test another base method - now only Movie 1 should be in the collection
    # Reset to a predictable state
    mock_radarr_client.get_movies.return_value = [
        Movie(id=101, title="Movie 1", tag_ids=[1, 4]),
        Movie(id=102, title="Movie 2", tag_ids=[2])
    ]
    
    movies = tag_manager.get_collection_media("Action")
    mock_radarr_client.get_movies.assert_called()
    assert len(movies) == 1
    assert movies[0].id == 101
    
    # Test reconcile_collections with valid movie id
    mock_radarr_client.reset_mock()
    # Add movie 105 back to the list for reconciliation
    mock_radarr_client.get_movies.return_value = [
        Movie(id=101, title="Movie 1", tag_ids=[1, 4]),
        Movie(id=102, title="Movie 2", tag_ids=[2]),
        Movie(id=105, title="Movie 5", tag_ids=[])
    ]
    # Need to set up get_movie for the reconciliation
    mock_radarr_client.get_movie.return_value = Movie(id=105, title="Movie 5", tag_ids=[])
    
    # Now reconcile
    tag_manager.reconcile_collections("Action", {105: True})
    mock_radarr_client.add_tag_to_movie.assert_called_with(105, 1)