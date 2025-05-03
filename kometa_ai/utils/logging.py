import os
import sys
import uuid
import json
import logging
from datetime import datetime, UTC
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional, MutableMapping


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self):
        super().__init__()
        self.run_id = str(uuid.uuid4())

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log
        """
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": self.run_id,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for key, value in record.extra.items():
                if key not in log_data:
                    log_data[key] = value

        return json.dumps(log_data)


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration.

    Args:
        debug: Enable debug logging
    """
    log_level = logging.DEBUG if debug else logging.INFO
    log_dir = os.path.join(os.getcwd(), "logs")

    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create file handler with rotation (10MB files, keep 10 files)
    log_file = os.path.join(log_dir, "kometa_ai.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=10
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use human-readable formats with timestamp and level for both normal and debug mode
    if debug:
        console_format = "%(asctime)s - %(levelname)s - %(message)s"
        console_handler.setFormatter(logging.Formatter(console_format))
    else:
        console_format = "%(asctime)s - %(levelname)s - %(message)s"
        console_handler.setFormatter(logging.Formatter(console_format))

    root_logger.addHandler(console_handler)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter to add extra fields to log records."""

    def __init__(self, logger: logging.Logger, extra: Optional[Dict[str, Any]] = None):
        """Initialize the logger adapter.

        Args:
            logger: The logger to adapt
            extra: Extra fields to add to all log records
        """
        if extra is None:
            extra = {}
        super().__init__(logger, extra)

    def process(self, msg: str, kwargs: MutableMapping[str, Any]) -> tuple[str, MutableMapping[str, Any]]:
        """Process the log record to add extra fields.

        Args:
            msg: The log message
            kwargs: Keyword arguments for the log record

        Returns:
            Tuple of (message, kwargs)
        """
        # Add extra fields to record
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # Handle case when self.extra might be None
        if self.extra:
            for key, value in self.extra.items():
                kwargs["extra"][key] = value

        return msg, kwargs
