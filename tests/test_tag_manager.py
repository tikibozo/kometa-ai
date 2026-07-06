import pytest
from unittest.mock import Mock

from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag
from kometa_ai.tag_manager import TagManager


@pytest.fixture
def mock_radarr_client():
    """Create a mock RadarrClient."""
    client = Mock(spec=RadarrClient)

    tags = [
        Tag(id=1, label="KAI-action"),
        Tag(id=2, label="KAI-comedy"),
    ]

    def get_or_create_tag(label):
        for tag in tags:
            if tag.label.lower() == label.lower():
                return tag
        new_tag = Tag(id=max(tag.id for tag in tags) + 1, label=label)
        tags.append(new_tag)
        return new_tag
    client.get_or_create_tag.side_effect = get_or_create_tag

    return client


@pytest.fixture
def tag_manager(mock_radarr_client):
    """Create a TagManager with a mock RadarrClient."""
    return TagManager(mock_radarr_client)


def test_reconcile_adds_and_removes(tag_manager, mock_radarr_client):
    """Movies gaining/losing membership get their tag added/removed."""
    movies = [
        Movie(id=101, title="Movie 1", tag_ids=[1]),   # member, stays
        Movie(id=102, title="Movie 2", tag_ids=[1]),   # member, drops out
        Movie(id=103, title="Movie 3", tag_ids=[]),    # not member, joins
        Movie(id=104, title="Movie 4", tag_ids=[]),    # not member, stays out
    ]

    changes = tag_manager.reconcile_collection_membership(
        collection_name="Action",
        tag="KAI-action",
        included_movie_ids=[101, 103],
        all_movies=movies,
    )

    actions = {c["movie_id"]: c["action"] for c in changes}
    assert actions == {103: "added", 102: "removed"}
    mock_radarr_client.add_tag_to_movie.assert_called_once_with(103, 1)
    mock_radarr_client.remove_tag_from_movie.assert_called_once_with(102, 1)


def test_reconcile_no_changes(tag_manager, mock_radarr_client):
    """No API calls when membership already matches."""
    movies = [
        Movie(id=101, title="Movie 1", tag_ids=[1]),
        Movie(id=102, title="Movie 2", tag_ids=[]),
    ]

    changes = tag_manager.reconcile_collection_membership(
        collection_name="Action",
        tag="KAI-action",
        included_movie_ids=[101],
        all_movies=movies,
    )

    assert changes == []
    mock_radarr_client.add_tag_to_movie.assert_not_called()
    mock_radarr_client.remove_tag_from_movie.assert_not_called()


def test_reconcile_creates_missing_tag(tag_manager, mock_radarr_client):
    """A new collection's tag is created on first reconcile."""
    movies = [Movie(id=101, title="Movie 1", tag_ids=[])]

    changes = tag_manager.reconcile_collection_membership(
        collection_name="Film Noir",
        tag="KAI-film-noir",
        included_movie_ids=[101],
        all_movies=movies,
    )

    mock_radarr_client.get_or_create_tag.assert_called_once_with("KAI-film-noir")
    assert changes[0]["action"] == "added"
