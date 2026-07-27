import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

from kometa_ai.__version__ import __version__
from kometa_ai.notification.email import EmailNotifier
from kometa_ai.notification.formatter import NotificationFormatter


class TestEmailNotifier:
    """Test the EmailNotifier class."""
    
    def test_initialization(self):
        """Test EmailNotifier initialization."""
        # With default/empty environment variables
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: 
                  "kometa-ai@localhost" if key == "NOTIFICATION_FROM" else None):
            notifier = EmailNotifier()
            assert notifier.smtp_server is None
            assert notifier.smtp_port == 25
            assert notifier.recipients == []
            assert notifier.from_address == "kometa-ai@localhost"
            assert notifier.can_send() is False
    
    def test_initialization_with_config(self):
        """Test EmailNotifier initialization with configuration."""
        # Mock the Config.get method to return our test values
        def mock_config_get(key, default=None):
            config = {
                "SMTP_SERVER": "smtp.example.com",
                "SMTP_PORT": "587",
                "NOTIFICATION_RECIPIENTS": "user1@example.com,user2@example.com",
                "SMTP_USERNAME": "testuser",
                "SMTP_PASSWORD": "testpass",
                "SMTP_USE_TLS": "true",
                "NOTIFICATION_FROM": "kometa@example.com"
            }
            return config.get(key, default)
        
        with patch("kometa_ai.config.Config.get", side_effect=mock_config_get), \
             patch("kometa_ai.config.Config.get_bool", return_value=True), \
             patch("kometa_ai.config.Config.get_int", return_value=587), \
             patch("kometa_ai.config.Config.get_list", return_value=["user1@example.com", "user2@example.com"]):
            
            notifier = EmailNotifier()
            
            # Verify configuration
            assert notifier.smtp_server == "smtp.example.com"
            assert notifier.smtp_port == 587
            assert notifier.recipients == ["user1@example.com", "user2@example.com"]
            assert notifier.smtp_username == "testuser"
            assert notifier.smtp_password == "testpass"
            assert notifier.use_tls is True
            assert notifier.from_address == "kometa@example.com"
            assert notifier.can_send() is True
    
    def test_can_send(self):
        """Test can_send method."""
        # Case 1: Missing SMTP server
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": None,
            "NOTIFICATION_RECIPIENTS": "user@example.com"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            assert notifier.can_send() is False
        
        # Case 2: Missing recipients
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "NOTIFICATION_RECIPIENTS": None
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_list", return_value=[]):
            notifier = EmailNotifier()
            assert notifier.can_send() is False
        
        # Case 3: Both present
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "NOTIFICATION_RECIPIENTS": "user@example.com"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            assert notifier.can_send() is True
    
    def test_should_send(self):
        """Test should_send method."""
        notifier = EmailNotifier()
        
        # Always send if there are changes
        assert notifier.should_send(has_changes=True, has_errors=False) is True
        
        # Always send if there are errors with send_on_errors_only
        notifier.send_on_errors_only = True
        assert notifier.should_send(has_changes=False, has_errors=True) is True
        
        # Don't send if no changes or errors, and not configured to send on no changes
        notifier.send_on_no_changes = False
        assert notifier.should_send(has_changes=False, has_errors=False) is False
        
        # Send if no changes but configured to send on no changes
        notifier.send_on_no_changes = True
        assert notifier.should_send(has_changes=False, has_errors=False) is True
    
    @patch("smtplib.SMTP")
    def test_send_notification_without_auth(self, mock_smtp):
        """Test send_notification without authentication."""
        # Setup
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "25",
            "NOTIFICATION_RECIPIENTS": "user@example.com",
            "NOTIFICATION_FROM": "kometa@example.com"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_int", return_value=25), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            
            # Test sending
            result = notifier.send_notification("Test Subject", "Test Message")
            
            # Verify
            assert result is True
            mock_smtp.assert_called_once_with("smtp.example.com", 25)
            mock_smtp_instance.login.assert_not_called()  # No auth
            mock_smtp_instance.sendmail.assert_called_once()
            args = mock_smtp_instance.sendmail.call_args[0]
            assert args[0] == "kometa@example.com"  # From
            assert args[1] == ["user@example.com"]  # To
            assert "Subject: Test Subject" in args[2]  # Content
            assert "Test Message" in args[2]  # Content
            mock_smtp_instance.quit.assert_called_once()
    
    @patch("smtplib.SMTP")
    def test_send_notification_with_auth(self, mock_smtp):
        """Test send_notification with authentication."""
        # Setup
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "587",
            "NOTIFICATION_RECIPIENTS": "user@example.com",
            "NOTIFICATION_FROM": "kometa@example.com",
            "SMTP_USERNAME": "testuser",
            "SMTP_PASSWORD": "testpass",
            "SMTP_USE_TLS": "true"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_int", return_value=587), \
        patch("kometa_ai.config.Config.get_bool", return_value=True), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            
            # Test sending
            result = notifier.send_notification("Test Subject", "Test Message")
            
            # Verify
            assert result is True
            mock_smtp.assert_called_once_with("smtp.example.com", 587)
            mock_smtp_instance.starttls.assert_called_once()  # TLS
            mock_smtp_instance.login.assert_called_once_with("testuser", "testpass")  # Auth
            mock_smtp_instance.sendmail.assert_called_once()
            mock_smtp_instance.quit.assert_called_once()
    
    @patch("smtplib.SMTP_SSL")
    def test_send_notification_with_ssl(self, mock_smtp_ssl):
        """Test send_notification with SSL."""
        # Setup
        mock_smtp_instance = MagicMock()
        mock_smtp_ssl.return_value = mock_smtp_instance
        
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "465",
            "NOTIFICATION_RECIPIENTS": "user@example.com",
            "NOTIFICATION_FROM": "kometa@example.com",
            "SMTP_USE_SSL": "true"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_int", return_value=465), \
        patch("kometa_ai.config.Config.get_bool", side_effect=lambda key, default=None: {
            "SMTP_USE_SSL": True,
            "SMTP_USE_TLS": False
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            
            # Test sending
            result = notifier.send_notification("Test Subject", "Test Message")
            
            # Verify
            assert result is True
            mock_smtp_ssl.assert_called_once()  # SSL
            mock_smtp_instance.sendmail.assert_called_once()
            mock_smtp_instance.quit.assert_called_once()
    
    def test_send_notification_without_config(self):
        """Test send_notification without proper configuration."""
        with patch("kometa_ai.config.Config.get", return_value=None), \
             patch("kometa_ai.config.Config.get_list", return_value=[]):
            notifier = EmailNotifier()
            
            # Test sending
            result = notifier.send_notification("Test Subject", "Test Message")
            
            # Verify
            assert result is False  # Should fail
    
    @patch("smtplib.SMTP")
    def test_send_notification_with_exception(self, mock_smtp):
        """Test send_notification with an exception."""
        # Setup
        mock_smtp.side_effect = Exception("Test SMTP Error")
        
        with patch("kometa_ai.config.Config.get", side_effect=lambda key, default=None: {
            "SMTP_SERVER": "smtp.example.com",
            "SMTP_PORT": "25",
            "NOTIFICATION_RECIPIENTS": "user@example.com"
        }.get(key, default)), \
        patch("kometa_ai.config.Config.get_int", return_value=25), \
        patch("kometa_ai.config.Config.get_list", return_value=["user@example.com"]):
            notifier = EmailNotifier()
            
            # Test sending
            result = notifier.send_notification("Test Subject", "Test Message")
            
            # Verify
            assert result is False  # Should fail
    
    def test_send_summary(self):
        """Test send_summary method."""
        # Setup
        notifier = EmailNotifier()
        
        # Mock the should_send and send_notification methods
        with patch.object(notifier, "should_send", return_value=True), \
             patch.object(notifier, "send_notification", return_value=True):
            # Test with changes
            result = notifier.send_summary(
                subject="Test Summary",
                message="Test Summary Message",
                has_changes=True,
                has_errors=False
            )
            
            # Verify
            assert result is True
            # The method is called with positional args rather than keyword args
            notifier.should_send.assert_called_once()
            # Check that it was called with the correct arguments, regardless of keyword/positional
            actual_call = notifier.send_notification.call_args
            assert actual_call[0][0] == "Test Summary"  # First positional arg
            assert actual_call[0][1] == "Test Summary Message"  # Second positional arg
        
        # Test without changes or errors (should not send)
        with patch.object(notifier, "should_send", return_value=False), \
             patch.object(notifier, "send_notification") as mock_send:
            result = notifier.send_summary(
                subject="Test Summary",
                message="Test Summary Message",
                has_changes=False,
                has_errors=False
            )
            
            # Verify
            assert result is False
            # The method is called with positional args rather than keyword args
            notifier.should_send.assert_called_once()
            mock_send.assert_not_called()  # Should not send


class TestNotificationFormatter:
    """Test the NotificationFormatter class."""
    
    def test_format_changes_by_collection(self):
        """Test _format_changes_by_collection."""
        # Sample changes
        changes = [
            {"collection": "Action", "action": "added", "title": "Movie 1", "movie_id": 1},
            {"collection": "Action", "action": "removed", "title": "Movie 2", "movie_id": 2},
            {"collection": "Drama", "action": "added", "title": "Movie 3", "movie_id": 3}
        ]
        
        # Format changes
        result = NotificationFormatter._format_changes_by_collection(changes)
        
        # Verify
        assert "Action" in result
        assert "Drama" in result
        assert len(result["Action"]["added"]) == 1
        assert len(result["Action"]["removed"]) == 1
        assert len(result["Drama"]["added"]) == 1
        assert len(result["Drama"]["removed"]) == 0
        
        # Verify specific changes
        assert result["Action"]["added"][0]["title"] == "Movie 1"
        assert result["Action"]["removed"][0]["title"] == "Movie 2"
        assert result["Drama"]["added"][0]["title"] == "Movie 3"
    
    def test_summary_rows(self):
        """_summary_rows returns one (collection, added, removed) row per
        changed collection, sorted by name."""
        changes = [
            {"collection": "Drama", "action": "added", "title": "M3", "movie_id": 3},
            {"collection": "Action", "action": "added", "title": "M1", "movie_id": 1},
            {"collection": "Action", "action": "removed", "title": "M2", "movie_id": 2},
        ]
        rows = NotificationFormatter._summary_rows(changes)
        assert rows == [("Action", 1, 1), ("Drama", 1, 0)]

    def test_format_summary(self):
        """Plain-text summary: overview line, at-a-glance table, detail, and a
        compact footer — no Markdown syntax."""
        changes = [
            {"collection": "Action", "action": "added", "title": "Movie 1", "movie_id": 1},
            {"collection": "Action", "action": "removed", "title": "Movie 2", "movie_id": 2},
            {"collection": "Drama", "action": "added", "title": "Movie 3", "movie_id": 3},
        ]
        errors = [
            {"context": "collection:Action", "timestamp": "2023-01-01T12:00:00Z", "message": "Error 1"}
        ]
        next_run_time = datetime(2023, 1, 2, 3, 0, 0)
        stats = {"Action": {"processed_movies": 10, "from_cache": 5, "total_cost": 0.01}}

        result = NotificationFormatter.format_summary(
            changes=changes, errors=errors, next_run_time=next_run_time,
            collection_stats=stats, version="1.0.0",
        )
        assert "Kometa-AI Report (v1.0.0)" in result
        assert "3 changes (+2/-1)" in result
        assert "1 errors" in result
        assert "next run 2023-01-02 03:00" in result
        assert "+ Movie 1 (1)" in result
        assert "- Movie 2 (2)" in result
        assert "-- Errors --" in result and "Error 1" in result
        assert "Processed 10 movies" in result
        assert "$0.0100" in result
        # no leftover Markdown noise
        assert "## " not in result
        assert "**" not in result

    def test_format_summary_truncated(self):
        """Overview shows the truncation note when >500 changes in one run."""
        changes = [
            {"collection": "C", "action": "added", "title": f"M{i}", "movie_id": i}
            for i in range(3)
        ]
        meta = {"truncated": True, "total_count": 620}
        result = NotificationFormatter.format_summary(
            changes=changes, errors=[], version="1.0.0", changes_metadata=meta)
        assert "620 changes" in result
        assert "showing most recent 3" in result

    def test_format_summary_html(self):
        """HTML summary: table layout, inline color styles, escaping, no scripts."""
        changes = [
            {"collection": "Action", "action": "added", "title": "Movie <1>", "movie_id": 1},
            {"collection": "Action", "action": "removed", "title": "Movie 2", "movie_id": 2},
        ]
        result = NotificationFormatter.format_summary_html(
            changes=changes, errors=[], version="1.0.0",
            collection_stats={"Action": {"processed_movies": 10, "total_cost": 0.0}},
        )
        assert result.startswith("<div")
        assert "<table" in result and "</table>" in result
        assert "Kometa-AI Report" in result
        assert "#1a7f37" in result  # green for added
        assert "#c9252d" in result  # red for removed
        # title HTML-escaped, no raw angle brackets or scripts
        assert "Movie &lt;1&gt;" in result
        assert "<script" not in result
        assert "Processed 10 movies" in result
        assert "subscription ($0)" in result

    def test_format_error_notification(self):
        """Plain-text critical-error notification."""
        result = NotificationFormatter.format_error_notification(
            error_context="test_context", error_message="Test error message",
            traceback="Traceback: line 1\n  line 2", version="1.0.0",
        )
        assert "Kometa-AI Error Report (v1.0.0)" in result
        assert "Error in test_context" in result
        assert "Test error message" in result
        assert "Traceback: line 1" in result

        result = NotificationFormatter.format_error_notification(
            error_context="test_context", error_message="Test error message", version="1.0.0")
        assert "Kometa-AI Error Report (v1.0.0)" in result
        assert "Traceback:" not in result


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])