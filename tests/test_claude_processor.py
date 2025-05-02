import os
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from kometa_ai.claude.processor import MovieProcessor
from kometa_ai.claude.client import ClaudeClient
from kometa_ai.claude.prompts import get_system_prompt, format_collection_prompt, format_movies_data
from kometa_ai.radarr.models import Movie
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

from datetime import datetime, UTC


# Load test data from the existing function
def load_test_data():
    test_dir = Path(__file__).parent.parent / "test_data"
    
    # Create test data directory if it doesn't exist
    if not test_dir.exists():
        test_dir.mkdir(parents=True)
    
    movies_file = test_dir / "synthetic_movies.json"
    collections_file = test_dir / "synthetic_collections.json"
    
    # Generate test data if it doesn't exist
    if not movies_file.exists() or not collections_file.exists():
        from test_data.synthetic_movies import synthetic_movies, synthetic_collections
    else:
        with open(movies_file, 'r') as f:
            synthetic_movies = json.load(f)
        
        with open(collections_file, 'r') as f:
            synthetic_collections = json.load(f)
    
    # Convert to model objects
    movies = [Movie.from_dict(movie_data) for movie_data in synthetic_movies]
    collections = [CollectionConfig.from_dict(c["name"], c) for c in synthetic_collections]
    
    return movies, collections


class TestPrompts:
    """Tests for prompt formatting functions."""
    
    def test_system_prompt(self):
        """Test the system prompt generation."""
        system_prompt = get_system_prompt()
        
        # Check for key elements
        assert "film expert" in system_prompt
        assert "categorizing movies" in system_prompt
        assert "Guidelines:" in system_prompt
        assert "JSON format" in system_prompt
        assert "collection_name" in system_prompt
        assert "decisions" in system_prompt
        assert "confidence" in system_prompt
    
    def test_collection_prompt(self):
        """Test collection-specific prompt formatting."""
        # Create a test collection
        collection = CollectionConfig(
            name="Test Collection",
            slug="test-collection",
            enabled=True,
            prompt="These are the criteria for the test collection.",
            confidence_threshold=0.75
        )
        
        prompt = format_collection_prompt(collection)
        
        # Check for key elements
        assert "Test Collection" in prompt
        assert "criteria for the test collection" in prompt
        assert "0.75" in prompt  # The confidence threshold
    
    def test_movies_data_formatting(self):
        """Test movie data formatting with various metadata fields."""
        # Create test movies with different available metadata
        movies = [
            Movie(
                id=1,
                title="Movie 1",
                year=2020,
                genres=["Action", "Adventure"],
                overview="A test movie overview"
            ),
            Movie(
                id=2,
                title="Movie 2",
                original_title="Original Title 2",
                year=2019,
                genres=["Drama"],
                overview="Another test movie",
                studio="Test Studio",
                runtime=120,
                imdb_id="tt1234567",
                tmdb_id=9876543
            )
        ]
        
        formatted_data = format_movies_data(movies)
        parsed_data = json.loads(formatted_data)
        
        # Check basic structure
        assert len(parsed_data) == 2
        assert parsed_data[0]["movie_id"] == 1
        assert parsed_data[0]["title"] == "Movie 1"
        assert parsed_data[0]["year"] == 2020
        
        # Check that optional fields are included when available
        assert "original_title" not in parsed_data[0]
        assert "original_title" in parsed_data[1]
        assert parsed_data[1]["original_title"] == "Original Title 2"
        assert parsed_data[1]["studio"] == "Test Studio"
        assert parsed_data[1]["runtime_minutes"] == 120
        assert parsed_data[1]["imdb_id"] == "tt1234567"
        assert parsed_data[1]["tmdb_id"] == 9876543


class TestMovieProcessor:
    """Tests for the MovieProcessor class."""
    
    @pytest.fixture
    def setup_processor(self, tmp_path):
        """Set up test environment for processor tests."""
        # Create state directory
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        
        # Create mock Claude client
        mock_client = MagicMock(spec=ClaudeClient)
        
        # Mock response from Claude
        mock_response = {
            "collection_name": "Test Collection",
            "decisions": [
                {
                    "movie_id": 1,
                    "title": "Movie 1",
                    "include": True,
                    "confidence": 0.95
                },
                {
                    "movie_id": 2,
                    "title": "Movie 2",
                    "include": False,
                    "confidence": 0.85
                },
                {
                    "movie_id": 3,
                    "title": "Movie 3",
                    "include": True,
                    "confidence": 0.65,
                    "reasoning": "This is a borderline case."
                }
            ]
        }
        
        mock_usage = {
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "total_cost": 0.05,
            "requests": 1,
            "start_time": datetime.now(UTC).isoformat(),
            "end_time": datetime.now(UTC).isoformat()
        }
        
        # Configure the mock to return our test data
        mock_client.classify_movies.return_value = (mock_response, mock_usage)
        
        # Create state manager
        state_manager = StateManager(str(state_dir))
        
        # Create test movies
        movies = [
            Movie(id=1, title="Movie 1"),
            Movie(id=2, title="Movie 2"),
            Movie(id=3, title="Movie 3")
        ]
        
        # Create test collection
        collection = CollectionConfig(
            name="Test Collection",
            slug="test-collection",
            enabled=True,
            prompt="Test criteria",
            confidence_threshold=0.7
        )
        
        # Create processor
        processor = MovieProcessor(mock_client, state_manager, batch_size=10)
        
        return {
            "processor": processor,
            "client": mock_client,
            "state_manager": state_manager,
            "movies": movies,
            "collection": collection
        }
    
    def test_process_collection_basic(self, setup_processor):
        """Test basic collection processing with all movies included."""
        processor = setup_processor["processor"]
        movies = setup_processor["movies"]
        collection = setup_processor["collection"]
        
        # Process the collection
        included, excluded, stats = processor.process_collection(collection, movies)
        
        # Check that movies were correctly classified
        assert len(included) == 1  # Only movie 1 has confidence > threshold
        assert len(excluded) == 2  # Movies 2 and 3
        assert 1 in included  # Movie 1 should be included
        assert 2 in excluded  # Movie 2 should be excluded
        assert 3 in excluded  # Movie 3 has confidence below threshold
        
        # Check that stats were recorded
        assert stats["processed_movies"] == 3
        assert stats["batches"] == 1
        assert stats["total_cost"] > 0
    
    def test_process_collection_disabled(self, setup_processor):
        """Test that disabled collections are skipped."""
        processor = setup_processor["processor"]
        movies = setup_processor["movies"]
        collection = setup_processor["collection"]
        
        # Disable the collection
        collection.enabled = False
        
        # Process the collection
        included, excluded, stats = processor.process_collection(collection, movies)
        
        # Check that no processing was done
        assert len(included) == 0
        assert len(excluded) == 0
        assert not setup_processor["client"].classify_movies.called
    
    def test_process_decisions(self, setup_processor):
        """Test the decision processing logic."""
        processor = setup_processor["processor"]
        state_manager = setup_processor["state_manager"]
        collection = setup_processor["collection"]
        
        # Create test movies
        movies = [
            Movie(id=1, title="Movie 1"),
            Movie(id=2, title="Movie 2")
        ]
        
        # Create test response
        response = {
            "collection_name": "Test Collection",
            "decisions": [
                {
                    "movie_id": 1,
                    "title": "Movie 1",
                    "include": True,
                    "confidence": 0.9
                },
                {
                    "movie_id": 2,
                    "title": "Movie 2",
                    "include": True,
                    "confidence": 0.6  # Below threshold
                }
            ]
        }
        
        # Process decisions
        included, excluded = processor._process_decisions(response, collection, movies)
        
        # Check results
        assert len(included) == 1
        assert len(excluded) == 1
        assert 1 in included
        assert 2 in excluded
        
        # Check that decisions were stored in state
        decision1 = state_manager.get_decision(1, "Test Collection")
        assert decision1 is not None
        assert decision1.include is True
        assert decision1.confidence == 0.9
        
        decision2 = state_manager.get_decision(2, "Test Collection")
        assert decision2 is not None
        assert decision2.include is True  # The raw decision is True
        assert decision2.confidence == 0.6  # But below threshold
    
    def test_get_collection_stats(self, setup_processor):
        """Test collection statistics retrieval."""
        processor = setup_processor["processor"]
        movies = setup_processor["movies"]
        collection = setup_processor["collection"]
        
        # Process a collection to generate stats
        processor.process_collection(collection, movies)
        
        # Get stats for the specific collection
        collection_stats = processor.get_collection_stats("Test Collection")
        assert collection_stats is not None
        assert "processed_movies" in collection_stats
        assert "total_cost" in collection_stats
        
        # Get all stats
        all_stats = processor.get_collection_stats()
        assert "Test Collection" in all_stats
    
    def test_incremental_processing(self, setup_processor):
        """Test the incremental processing logic with metadata changes."""
        processor = setup_processor["processor"]
        state_manager = setup_processor["state_manager"]
        movies = setup_processor["movies"]
        collection = setup_processor["collection"]
        client = setup_processor["client"]
        
        # Add a decision to the state to simulate previous processing
        decision = DecisionRecord(
            movie_id=1,
            collection_name="Test Collection",
            include=True,
            confidence=0.8,
            metadata_hash="original_hash",
            tag="KAI-test-collection",
            timestamp=datetime.now(UTC).isoformat()
        )
        state_manager.set_decision(decision)
        
        # Patch the calculate_metadata_hash method to return a different hash
        with patch.object(
            Movie, 'calculate_metadata_hash', 
            side_effect=lambda: "changed_hash"
        ):
            # Process with force_refresh=False
            processor.force_refresh = False
            included, excluded, stats = processor.process_collection(collection, movies)
            
            # All movies should be reprocessed because the hash changed
            assert client.classify_movies.call_count == 1  # One batch
            assert stats["processed_movies"] > 0  # Some movies were processed


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])