import os
import json
import logging
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for Kometa-AI.

    Loads configuration from environment variables and provides
    access to configuration values with defaults.
    """

    # Environment variable defaults
    DEFAULTS = {
        "RADARR_URL": None,  # Required
        "RADARR_API_KEY": None,  # Required
        "CLAUDE_API_KEY": None,  # Required
        "DEBUG_LOGGING": "false",
        "SMTP_SERVER": None,
        "SMTP_PORT": "25",
        "NOTIFICATION_RECIPIENTS": None,
        "SCHEDULE_INTERVAL": "1d",
        "SCHEDULE_START_TIME": "03:00",
        "TZ": "UTC",
    }

    # Required configuration variables
    REQUIRED = ["RADARR_URL", "RADARR_API_KEY", "CLAUDE_API_KEY"]

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.config = {}
        self._load_from_env()
        self._validate()

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get a configuration value from environment variables.

        Args:
            key: The configuration key (environment variable name)
            default: Default value if not found

        Returns:
            The configuration value or default
        """
        return os.environ.get(key, Config.DEFAULTS.get(key, default))

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Get a boolean configuration value.

        Args:
            key: The configuration key
            default: Default value if not found

        Returns:
            The boolean value (true/false, yes/no, 1/0)
        """
        value = Config.get(key, str(default))
        if value is None:
            return default
        return value.lower() in ("true", "yes", "1", "t", "y")

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        """Get an integer configuration value.

        Args:
            key: The configuration key
            default: Default value if not found

        Returns:
            The integer value or default
        """
        value = Config.get(key, default)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    @staticmethod
    def get_list(key: str, default: Optional[List[str]] = None) -> List[str]:
        """Get a list configuration value from comma-separated string.

        Args:
            key: The configuration key
            default: Default value if not found

        Returns:
            The list of values
        """
        if default is None:
            default = []

        value = Config.get(key, None)
        if not value:
            return default

        return [item.strip() for item in value.split(",")]

    def _load_from_env(self) -> None:
        """Load configuration from environment variables."""
        for key in self.DEFAULTS.keys():
            self.config[key] = self.get(key)

    def _validate(self) -> None:
        """Validate required configuration values are present."""
        missing = []
        for key in self.REQUIRED:
            if not self.config.get(key):
                missing.append(key)

        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
            # Don't raise an exception, just log the error

    def dump(self) -> None:
        """Print the current configuration (with sensitive values masked)."""
        # Create a copy to mask sensitive values
        display_config = {}
        for key, value in self.config.items():
            if key.endswith(("API_KEY", "PASSWORD", "SECRET")):
                display_config[key] = "********" if value else None
            else:
                display_config[key] = value

        print(json.dumps(display_config, indent=2))

    def as_dict(self) -> Dict[str, Any]:
        """Get configuration as a dictionary.

        Returns:
            Dictionary of configuration values
        """
        return self.config.copy()
