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
    
    def test_format_collection_changes(self):
        """Test _format_collection_changes."""
        # Sample changes
        added = [
            {"title": "Movie 1", "movie_id": 1},
            {"title": "Movie 2", "movie_id": 2}
        ]
        removed = [
            {"title": "Movie 3", "movie_id": 3}
        ]
        
        # Format collection changes
        result = NotificationFormatter._format_collection_changes("Action", added, removed)
        
        # Verify format
        assert "### Action" in result
        assert "**Added**: 2" in result
        assert "**Removed**: 1" in result
        assert "- Movie 1 (1)" in result
        assert "- Movie 2 (2)" in result
        assert "- Movie 3 (3)" in result
        
        # Test with no changes
        result = NotificationFormatter._format_collection_changes("Empty", [], [])
        assert "### Empty" in result
        assert "No changes" in result
    
    def test_format_errors(self):
        """Test _format_errors."""
        # Sample errors
        errors = [
            {"context": "collection:Action", "timestamp": "2023-01-01T12:00:00Z", "message": "Error 1"},
            {"context": "collection:Action", "timestamp": "2023-01-01T13:00:00Z", "message": "Error 2"},
            {"context": "collection:Drama", "timestamp": "2023-01-01T14:00:00Z", "message": "Error 3"}
        ]
        
        # Format errors
        result = NotificationFormatter._format_errors(errors)
        
        # Verify format
        assert "### collection:Action" in result
        assert "### collection:Drama" in result
        assert "- 2023-01-01: Error 1" in result
        assert "- 2023-01-01: Error 2" in result
        assert "- 2023-01-01: Error 3" in result
        
        # Test with no errors
        result = NotificationFormatter._format_errors([])
        assert "No errors encountered" in result
    
    def test_format_collection_stats(self):
        """Test _format_collection_stats."""
        # Sample stats
        stats = {
            "Action": {
                "processed_movies": 10,
                "from_cache": 5,
                "total_input_tokens": 1000,
                "total_output_tokens": 500,
                "total_cost": 0.01
            },
            "Drama": {
                "processed_movies": 20,
                "from_cache": 10,
                "total_input_tokens": 2000,
                "total_output_tokens": 1000,
                "total_cost": 0.02
            }
        }
        
        # Format stats
        result = NotificationFormatter._format_collection_stats(stats)
        
        # Verify format
        assert "### Summary" in result
        assert "### Action" in result
        assert "### Drama" in result
        assert "- Total processed: 30 movies" in result
        assert "- Collections processed: 2" in result
        assert "- Total cost: $0.0300" in result
        assert "- Processed: 10 movies" in result
        assert "- From cache: 5 movies" in result
        assert "- API cost: $0.0100" in result
        
        # Test with no stats
        result = NotificationFormatter._format_collection_stats({})
        assert "No statistics available" in result
    
    def test_format_summary(self):
        """Test format_summary."""
        # Sample data
        changes = [
            {"collection": "Action", "action": "added", "title": "Movie 1", "movie_id": 1},
            {"collection": "Drama", "action": "added", "title": "Movie 2", "movie_id": 2}
        ]
        errors = [
            {"context": "collection:Action", "timestamp": "2023-01-01T12:00:00Z", "message": "Error 1"}
        ]
        next_run_time = datetime(2023, 1, 2, 3, 0, 0)
        stats = {
            "Action": {
                "processed_movies": 10,
                "from_cache": 5,
                "total_cost": 0.01
            }
        }
        
        # Format summary
        result = NotificationFormatter.format_summary(
            changes=changes,
            errors=errors,
            next_run_time=next_run_time,
            collection_stats=stats,
            version="1.0.0"
        )
        
        # Verify format
        assert "# Kometa-AI Summary (v1.0.0)" in result
        assert "## Overview" in result
        assert "- Total changes: 2" in result
        assert "- Errors: 1" in result
        assert "- Next scheduled run: 2023-01-02 03:00:00" in result
        assert "## Changes by Collection" in result
        assert "## Errors" in result
        assert "## Processing Statistics" in result
        
        # Test without changes
        result = NotificationFormatter.format_summary(
            changes=[],
            errors=[],
            next_run_time=next_run_time,
            version="1.0.0"
        )
        assert "# Kometa-AI Summary (v1.0.0)" in result
        assert "No changes were made in this run" in result
    
    def test_format_error_notification(self):
        """Test format_error_notification."""
        # Format error notification
        result = NotificationFormatter.format_error_notification(
            error_context="test_context",
            error_message="Test error message",
            traceback="Traceback: line 1\n  line 2\n  line 3",
            version="1.0.0"
        )
        
        # Verify format
        assert "# Kometa-AI Error Report (v1.0.0)" in result
        assert "## Error in test_context" in result
        assert "**Error message**: Test error message" in result
        assert "## Traceback" in result
        assert "```" in result
        assert "Traceback: line 1" in result
        assert "## System Information" in result
        assert "- Version: 1.0.0" in result
        
        # Test without traceback
        result = NotificationFormatter.format_error_notification(
            error_context="test_context",
            error_message="Test error message",
            version="1.0.0"
        )
        assert "# Kometa-AI Error Report (v1.0.0)" in result
        assert "## Error in test_context" in result
        assert "**Error message**: Test error message" in result
        assert "## Traceback" not in result


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])