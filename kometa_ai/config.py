import os
import json
import logging
from typing import Any, Optional, List

from kometa_ai.claude.client import DEFAULT_MODEL

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for Kometa-AI.

    Reads configuration from environment variables and provides
    access to configuration values with defaults.
    """

    # Environment variable defaults
    DEFAULTS = {
        "RADARR_URL": None,  # Required
        "RADARR_API_KEY": None,  # Required
        "CLAUDE_API_KEY": None,  # Required for the api backend
        "CLAUDE_BACKEND": "api",  # "api" (Anthropic API key) or "cli" (claude CLI / subscription)
        "CLAUDE_MODEL": DEFAULT_MODEL,  # Optional: override default Claude model
        # Soft per-run cap on movies sent to Claude across all collections
        # (Lever 2). 0 = no cap. Paces the backfill of new/changed collections
        # on a large library into a predictable, bounded spend per run.
        "MAX_EVALS_PER_RUN": "0",
        "DEBUG_LOGGING": "false",
        "SMTP_SERVER": None,
        "SMTP_PORT": "25",
        "NOTIFICATION_RECIPIENTS": None,
        "NOTIFICATION_FROM": "kometa-ai@localhost",
        "SCHEDULE_INTERVAL": "1d",
        "SCHEDULE_START_TIME": "03:00",
        "TZ": "UTC",
    }

    # Required configuration variables (Claude auth is backend-dependent
    # and validated where the client is built)
    REQUIRED = ["RADARR_URL", "RADARR_API_KEY"]

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

    @staticmethod
    def dump() -> None:
        """Print the current configuration (with sensitive values masked)."""
        display_config = {}
        for key in Config.DEFAULTS:
            value = Config.get(key)
            if key.endswith(("API_KEY", "PASSWORD", "SECRET")):
                display_config[key] = "********" if value else None
            else:
                display_config[key] = value

        missing = [key for key in Config.REQUIRED if not Config.get(key)]
        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")

        print(json.dumps(display_config, indent=2))
