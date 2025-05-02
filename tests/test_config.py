import os
import pytest
from kometa_ai.config import Config


class TestConfig:
    """Tests for the Config class."""
    
    def test_get(self, monkeypatch):
        """Test getting config values."""
        monkeypatch.setenv("TEST_KEY", "test_value")
        assert Config.get("TEST_KEY") == "test_value"
    
    def test_get_with_default(self):
        """Test getting config with default."""
        assert Config.get("NONEXISTENT_KEY", "default") == "default"
    
    def test_get_bool(self, monkeypatch):
        """Test getting boolean config values."""
        monkeypatch.setenv("TEST_BOOL_TRUE", "true")
        monkeypatch.setenv("TEST_BOOL_YES", "yes")
        monkeypatch.setenv("TEST_BOOL_1", "1")
        monkeypatch.setenv("TEST_BOOL_FALSE", "false")
        
        assert Config.get_bool("TEST_BOOL_TRUE") is True
        assert Config.get_bool("TEST_BOOL_YES") is True
        assert Config.get_bool("TEST_BOOL_1") is True
        assert Config.get_bool("TEST_BOOL_FALSE") is False
        assert Config.get_bool("NONEXISTENT_BOOL") is False
        assert Config.get_bool("NONEXISTENT_BOOL", True) is True
    
    def test_get_int(self, monkeypatch):
        """Test getting integer config values."""
        monkeypatch.setenv("TEST_INT", "42")
        monkeypatch.setenv("TEST_INVALID_INT", "not_an_int")
        
        assert Config.get_int("TEST_INT") == 42
        assert Config.get_int("TEST_INVALID_INT") == 0
        assert Config.get_int("TEST_INVALID_INT", 10) == 10
        assert Config.get_int("NONEXISTENT_INT", 5) == 5
    
    def test_get_list(self, monkeypatch):
        """Test getting list config values."""
        monkeypatch.setenv("TEST_LIST", "item1,item2, item3")
        
        assert Config.get_list("TEST_LIST") == ["item1", "item2", "item3"]
        assert Config.get_list("NONEXISTENT_LIST") == []
        assert Config.get_list("NONEXISTENT_LIST", ["default"]) == ["default"]
    
    def test_initialization(self, monkeypatch):
        """Test config initialization."""
        # Set required env vars
        monkeypatch.setenv("RADARR_URL", "http://radarr:7878")
        monkeypatch.setenv("RADARR_API_KEY", "api_key")
        monkeypatch.setenv("CLAUDE_API_KEY", "claude_key")
        
        cfg = Config()
        assert cfg.config["RADARR_URL"] == "http://radarr:7878"
        assert cfg.config["RADARR_API_KEY"] == "api_key"
        assert cfg.config["CLAUDE_API_KEY"] == "claude_key"
    
    def test_as_dict(self, monkeypatch):
        """Test getting config as dict."""
        monkeypatch.setenv("RADARR_URL", "http://radarr:7878")
        monkeypatch.setenv("RADARR_API_KEY", "api_key")
        monkeypatch.setenv("CLAUDE_API_KEY", "claude_key")
        
        cfg = Config()
        config_dict = cfg.as_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["RADARR_URL"] == "http://radarr:7878"
        assert config_dict["RADARR_API_KEY"] == "api_key"