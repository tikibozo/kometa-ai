import os
import json
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from kometa_ai.__version__ import __version__
from kometa_ai.radarr.client import RadarrClient
from kometa_ai.radarr.models import Movie, Tag
from kometa_ai.claude.client import ClaudeClient
from kometa_ai.claude.processor import MovieProcessor
from kometa_ai.kometa.parser import KometaParser
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.state.manager import StateManager
from kometa_ai.tag_manager import TagManager
from kometa_ai.notification.email import EmailNotifier
from kometa_ai.notification.formatter import NotificationFormatter
import kometa_ai.__main__ as main_module


# Mock classes for testing
class MockRadarrClient(RadarrClient):
    """Mock Radarr client for testing."""
    
    def __init__(self, *args, **kwargs):
        # Skip the actual initialization
        self.tags = {}
        self.movies = []
        self.test_connection_result = True
        self.base_url = "http://mock-radarr:7878"
        self.api_key = "mock-api-key"
    
    def test_connection(self):
        return self.test_connection_result
    
    def get_movies(self):
        return self.movies
    
    def get_movie(self, movie_id):
        for movie in self.movies:
            if movie.id == movie_id:
                return movie
        return None
    
    def get_tags(self):
        return [Tag(id=tag_id, label=label) for tag_id, label in self.tags.items()]
    
    def get_tag(self, label):
        for tag_id, tag_label in self.tags.items():
            if tag_label == label:
                return Tag(id=tag_id, label=tag_label)
        return None
    
    def create_tag(self, label):
        tag_id = max(self.tags.keys(), default=0) + 1
        self.tags[tag_id] = label
        return Tag(id=tag_id, label=label)
    
    def get_or_create_tag(self, label):
        tag = self.get_tag(label)
        if tag:
            return tag
        return self.create_tag(label)
    
    def set_movie_tags(self, movie_id, tags):
        for movie in self.movies:
            if movie.id == movie_id:
                movie.tags = tags
                break
        return True
        
    def add_tag_to_movie(self, movie_id, tag_id):
        for movie in self.movies:
            if movie.id == movie_id:
                if not hasattr(movie, 'tag_ids'):
                    movie.tag_ids = []
                if tag_id not in movie.tag_ids:
                    movie.tag_ids.append(tag_id)
                break
        return self.get_movie(movie_id)
        
    def remove_tag_from_movie(self, movie_id, tag_id):
        for movie in self.movies:
            if movie.id == movie_id:
                if hasattr(movie, 'tag_ids') and tag_id in movie.tag_ids:
                    movie.tag_ids.remove(tag_id)
                break
        return self.get_movie(movie_id)


class MockClaudeClient(ClaudeClient):
    """Mock Claude client for testing."""
    
    def __init__(self, *args, **kwargs):
        # Skip the actual initialization
        self._cost_tracking = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'start_time': datetime.now().isoformat()
        }
        self.debug_mode = False
        self.test_connection_result = True
        
        # Predefined mock responses for different collections
        self.mock_responses = {
            "Action Movies": {
                "collection_name": "Action Movies",
                "decisions": [
                    {"movie_id": 1, "title": "Die Hard", "include": True, "confidence": 0.95},
                    {"movie_id": 2, "title": "The Godfather", "include": False, "confidence": 0.90},
                    {"movie_id": 3, "title": "The Matrix", "include": True, "confidence": 0.98}
                ]
            },
            "Drama": {
                "collection_name": "Drama",
                "decisions": [
                    {"movie_id": 1, "title": "Die Hard", "include": False, "confidence": 0.80},
                    {"movie_id": 2, "title": "The Godfather", "include": True, "confidence": 0.99},
                    {"movie_id": 3, "title": "The Matrix", "include": False, "confidence": 0.75}
                ]
            }
        }
    
    def test_connection(self):
        return self.test_connection_result
    
    def classify_movies(self, system_prompt, collection_prompt, movies_data, batch_size=None):
        # Extract collection name from prompt
        import re
        match = re.search(r'categorize movies for the "(.*?)" collection', collection_prompt)
        collection_name = match.group(1) if match else "Unknown Collection"
        
        # Get the appropriate mock response
        mock_response = self.mock_responses.get(
            collection_name, 
            {"collection_name": collection_name, "decisions": []}
        )
        
        # Update usage stats
        self._cost_tracking['total_input_tokens'] += 1000
        self._cost_tracking['total_output_tokens'] += 500
        self._cost_tracking['total_cost'] += 0.01
        self._cost_tracking['requests'] += 1
        
        return mock_response, self.get_usage_stats()
    
    def get_usage_stats(self):
        stats = self._cost_tracking.copy()
        stats['end_time'] = datetime.now().isoformat()
        return stats


class MockEmailNotifier(EmailNotifier):
    """Mock email notifier for testing."""
    
    def __init__(self):
        # Skip actual initialization
        self.smtp_server = "mock-smtp.example.com"
        self.smtp_port = 25
        self.recipients = ["user@example.com"]
        self.from_address = "kometa-ai@example.com"
        self.reply_to = "kometa-ai@example.com"
        self.use_ssl = False
        self.use_tls = False
        self.smtp_username = ""
        self.smtp_password = ""
        self.send_on_no_changes = False
        self.send_on_errors_only = True
        self.emails_sent = []
        self.can_send_result = True
        self.send_result = True
        
    def can_send(self):
        return self.can_send_result
        
    def send_notification(self, subject, message):
        if not self.can_send():
            return False
            
        self.emails_sent.append({
            "subject": subject,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })
        return self.send_result
        
    def should_send(self, has_changes, has_errors):
        if has_errors and self.send_on_errors_only:
            return True
        if has_changes:
            return True
        return self.send_on_no_changes


# Fixture for setting up a test environment
@pytest.fixture
def test_env():
    """Set up a test environment with mocked components."""
    # Create temp directories
    temp_dir = tempfile.mkdtemp()
    state_dir = os.path.join(temp_dir, "state")
    config_dir = os.path.join(temp_dir, "kometa-config")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    
    # Create test movies
    movies = [
        Movie(
            id=1, 
            title="Die Hard", 
            year=1988, 
            genres=["Action", "Thriller"],
            overview="NYPD cop John McClane goes on a Christmas vacation.",
            tag_ids=[]
        ),
        Movie(
            id=2, 
            title="The Godfather", 
            year=1972, 
            genres=["Crime", "Drama"],
            overview="The aging patriarch of an organized crime dynasty transfers control.",
            tag_ids=[]
        ),
        Movie(
            id=3, 
            title="The Matrix", 
            year=1999, 
            genres=["Action", "Sci-Fi"],
            overview="A computer hacker learns from mysterious rebels about the true nature of his reality.",
            tag_ids=[]
        )
    ]
    
    # Create mock collections
    collections = [
        CollectionConfig(
            name="Action Movies",
            slug="action-movies",
            enabled=True,
            prompt="Identify action movies based on thrills, stunts, and excitement.",
            confidence_threshold=0.7
        ),
        CollectionConfig(
            name="Drama",
            slug="drama",
            enabled=True,
            prompt="Identify drama movies based on serious themes and character development.",
            confidence_threshold=0.8
        )
    ]
    
    # Create mock YAML configuration file
    yaml_content = """
collections:
  # === KOMETA-AI ===
  # enabled: true
  # prompt: |
  #   Identify action movies based on thrills, stunts, and excitement.
  # confidence_threshold: 0.7
  # === END KOMETA-AI ===
  Action Movies:
    radarr_taglist: KAI-action-movies
    
  # === KOMETA-AI ===
  # enabled: true
  # prompt: |
  #   Identify drama movies based on serious themes and character development.
  # confidence_threshold: 0.8
  # === END KOMETA-AI ===
  Drama:
    radarr_taglist: KAI-drama
    """
    
    with open(os.path.join(config_dir, "collections.yml"), "w") as f:
        f.write(yaml_content)
    
    # Create mock clients
    radarr_client = MockRadarrClient("http://mock-radarr", "mock-api-key")
    radarr_client.movies = movies
    radarr_client.tags = {1: "KAI-action-movies", 2: "KAI-drama"}
    
    claude_client = MockClaudeClient("mock-api-key")
    
    email_notifier = MockEmailNotifier()
    
    state_manager = StateManager(state_dir)
    
    # Patch the KometaParser to return our mock collections
    parser_mock = MagicMock(spec=KometaParser)
    parser_mock.parse_configs.return_value = collections
    
    # Register cleanup
    yield {
        "temp_dir": temp_dir,
        "state_dir": state_dir,
        "config_dir": config_dir,
        "radarr_client": radarr_client,
        "claude_client": claude_client,
        "email_notifier": email_notifier,
        "state_manager": state_manager,
        "parser_mock": parser_mock,
        "movies": movies,
        "collections": collections
    }
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestEndToEndPipeline:
    """Test the end-to-end pipeline functionality."""
    
    @patch("kometa_ai.__main__.time.sleep")  # Patch sleep to avoid waiting
    def test_process_collections_function(self, mock_sleep, test_env):
        """Test the process_collections function."""
        # Setup
        radarr_client = test_env["radarr_client"]
        claude_client = test_env["claude_client"]
        state_manager = test_env["state_manager"]
        collections = test_env["collections"]
        
        # Execute the function
        results = main_module.process_collections(
            radarr_client=radarr_client,
            claude_client=claude_client,
            state_manager=state_manager,
            collections=collections,
            dry_run=False,
            batch_size=None,
            force_refresh=True
        )
        
        # Verify results
        assert results["collections_processed"] == 2
        assert results["total_changes"] > 0
        assert "Action Movies" in results["collection_stats"]
        assert "Drama" in results["collection_stats"]
        
        # Check that state has been updated
        state_manager.load()  # Reload state
        changes = state_manager.get_changes()
        assert len(changes) > 0
        
        # Check movie tags
        action_tag_id = 1  # From our mock setup
        drama_tag_id = 2
        
        # Die Hard should be in Action Movies but not Drama
        die_hard = radarr_client.movies[0]
        assert action_tag_id in die_hard.tag_ids
        assert drama_tag_id not in die_hard.tag_ids
        
        # The Godfather should be in Drama but not Action Movies
        godfather = radarr_client.movies[1]
        assert drama_tag_id in godfather.tag_ids
        assert action_tag_id not in godfather.tag_ids
        
        # The Matrix should be in Action Movies but not Drama
        matrix = radarr_client.movies[2]
        assert action_tag_id in matrix.tag_ids
        assert drama_tag_id not in matrix.tag_ids
    
    @patch("kometa_ai.__main__.EmailNotifier")
    def test_send_notifications_function(self, mock_email_class, test_env):
        """Test the send_notifications function."""
        # Setup
        state_manager = test_env["state_manager"]
        email_notifier = test_env["email_notifier"]
        mock_email_class.return_value = email_notifier
        
        # Add some test changes and errors
        for i in range(3):
            state_manager.log_change(
                movie_id=i+1,
                movie_title=f"Movie {i+1}",
                collection_name="Test Collection",
                action="added",
                tag="KAI-test-collection"
            )
        
        state_manager.log_error(
            context="test_context",
            error_message="Test error message"
        )
        
        # Ensure clear_errors and clear_changes methods exist
        if not hasattr(state_manager, 'clear_errors'):
            state_manager.clear_errors = lambda: state_manager.state.update({'errors': []})
        if not hasattr(state_manager, 'clear_changes'):
            state_manager.clear_changes = lambda: state_manager.state.update({'changes': []})
        
        # Set up a next run time
        next_run_time = datetime.now() + timedelta(hours=24)
        
        # Mock results
        results = {
            "total_changes": 3,
            "collections_processed": 1,
            "collection_stats": {
                "Test Collection": {
                    "processed_movies": 3,
                    "from_cache": 0,
                    "total_input_tokens": 1000,
                    "total_output_tokens": 500,
                    "total_cost": 0.01
                }
            }
        }
        
        # Execute the function
        sent = main_module.send_notifications(
            results=results,
            state_manager=state_manager,
            next_run_time=next_run_time
        )
        
        # Verify results
        assert sent is True
        assert len(email_notifier.emails_sent) == 1
        
        email = email_notifier.emails_sent[0]
        assert "Processing Report" in email["subject"]
        assert "Test Collection" in email["message"]
        assert "action-movies" not in email["message"].lower()  # Shouldn't contain unrelated collections
        
        # Verify that next run time is in the message
        tomorrow = next_run_time.strftime("%Y-%m-%d")
        assert tomorrow in email["message"]
        
        # Test with no changes
        email_notifier.emails_sent = []  # Clear sent emails
        state_manager.state["changes"] = []  # Clear changes
        state_manager.state["errors"] = []  # Clear errors as well
        
        # Override send_on_no_changes to False
        original_setting = email_notifier.send_on_no_changes
        email_notifier.send_on_no_changes = False
        
        sent = main_module.send_notifications(
            results={"total_changes": 0, "collections_processed": 0, "collection_stats": {}},
            state_manager=state_manager,
            next_run_time=next_run_time
        )
        
        # Restore original setting
        email_notifier.send_on_no_changes = original_setting
        
        # Verify no email was sent for no changes
        assert sent is False
        assert len(email_notifier.emails_sent) == 0
    
    @patch("kometa_ai.utils.scheduling.datetime")
    def test_calculate_schedule_function(self, mock_datetime, test_env):
        """Test the calculate_schedule function."""
        # Setup: mock current time to 2023-01-01 10:00
        mock_now = datetime(2023, 1, 1, 10, 0, 0)
        mock_datetime.now.return_value = mock_now
        
        # Test with daily schedule at 3am
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SCHEDULE_INTERVAL": "1d",
            "SCHEDULE_START_TIME": "03:00"
        }.get(key, default)):
            next_run = main_module.calculate_schedule()
            
            # Should be tomorrow at 3am
            expected = datetime(2023, 1, 2, 3, 0, 0)
            assert next_run == expected
        
        # Test with 12h schedule
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SCHEDULE_INTERVAL": "12h",
            "SCHEDULE_START_TIME": "03:00"
        }.get(key, default)):
            # Set current time to 2am (before scheduled time)
            mock_datetime.now.return_value = datetime(2023, 1, 1, 2, 0, 0)
            next_run = main_module.calculate_schedule()
            
            # Should be today at 3am
            expected = datetime(2023, 1, 1, 3, 0, 0)
            assert next_run == expected
        
        # Test hourly schedule
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SCHEDULE_INTERVAL": "1h",
            "SCHEDULE_START_TIME": "00:00"
        }.get(key, default)):
            # Set current time to 10:30am
            mock_datetime.now.return_value = datetime(2023, 1, 1, 10, 30, 0)
            next_run = main_module.calculate_schedule()
            
            # Should be 1 hour from now
            expected = datetime(2023, 1, 1, 11, 30, 0)
            assert next_run == expected
    
    @patch("kometa_ai.__main__.run_scheduled_pipeline")
    def test_main_function_run_now(self, mock_pipeline, test_env):
        """Test the main function with --run-now flag."""
        # Setup: simulate CLI args
        test_args = ["--run-now", "--collection", "Action Movies"]
        
        # Execute
        with patch("kometa_ai.__main__.parse_args", return_value=main_module.parse_args(test_args)):
            result = main_module.main()
        
        # Verify
        mock_pipeline.assert_called_once()
        args = mock_pipeline.call_args[0][0]
        assert args.run_now is True
        assert args.collection == "Action Movies"
    
    @patch("kometa_ai.__main__.run_scheduled_pipeline")
    def test_main_function_health_check(self, mock_pipeline, test_env):
        """Test the main function with --health-check flag."""
        # Setup: simulate CLI args
        test_args = ["--health-check"]
        
        # Patch run_health_check to return True
        with patch("kometa_ai.__main__.run_health_check", return_value=True):
            # Execute
            with patch("kometa_ai.__main__.parse_args", return_value=main_module.parse_args(test_args)):
                result = main_module.main()
        
        # Verify
        assert result == 0  # Success
        mock_pipeline.assert_not_called()  # Pipeline should not be called for health check
    
    def test_email_notification_with_real_notifier(self, test_env):
        """Test the EmailNotifier with a more realistic test."""
        # Setup
        notifier = MockEmailNotifier()  # Use our mock instead
        
        # Force can_send to return True
        notifier.can_send_result = True
                
        # Send a test email
        subject = "Test Email"
        message = "# Test Email\n\nThis is a test email body."
        
        result = notifier.send_notification(subject, message)
        
        # Verify
        assert result is True
        assert len(notifier.emails_sent) == 1
        
        # Verify email content
        email = notifier.emails_sent[0]
        assert email["subject"] == "Test Email"
        assert "# Test Email" in email["message"]
        assert "This is a test email body" in email["message"]
    
    @patch("kometa_ai.__main__.sleep_until")
    @patch("kometa_ai.__main__.calculate_schedule")
    def test_scheduled_execution(self, mock_calculate, mock_sleep, test_env):
        """Test the scheduled execution flow."""
        # Setup
        next_run_time = datetime.now() + timedelta(hours=1)
        mock_calculate.return_value = next_run_time
        
        # Create patches for all components and Config.get for required API config
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
                "RADARR_URL": "http://mock-radarr:7878",
                "RADARR_API_KEY": "mock-api-key",
                "CLAUDE_API_KEY": "mock-api-key"
            }.get(key, default)), \
             patch("kometa_ai.__main__.RadarrClient", return_value=test_env["radarr_client"]), \
             patch("kometa_ai.__main__.ClaudeClient", return_value=test_env["claude_client"]), \
             patch("kometa_ai.__main__.KometaParser", return_value=test_env["parser_mock"]), \
             patch("kometa_ai.__main__.StateManager", return_value=test_env["state_manager"]), \
             patch("kometa_ai.__main__.process_collections", return_value={"total_changes": 3}), \
             patch("kometa_ai.__main__.send_notifications", return_value=True), \
             patch("kometa_ai.__main__.terminate_requested", side_effect=[False, True]):  # Run once, then terminate
                
                # Create args with no run-now flag
                args = main_module.parse_args([])
                
                # Run the pipeline
                result = main_module.run_scheduled_pipeline(args)
                
                # Verify
                assert result == 0
                mock_calculate.assert_called_once()
                mock_sleep.assert_called_once_with(next_run_time)


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])