import re
import time
import logging
from typing import Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def parse_interval(interval_str: str) -> Tuple[int, str]:
    """Parse a time interval string into a value and unit.

    Args:
        interval_str: Interval string like "1h", "1d", "1w", "1mo"

    Returns:
        Tuple of (value, unit)

    Raises:
        ValueError: If the interval string is invalid
    """
    match = re.match(r"^(\d+)([hdwm]|mo)$", interval_str.lower())
    if not match:
        raise ValueError(
            f"Invalid interval: {interval_str}. Expected format: Xh, Xd, Xw, Xmo (e.g., 1h, 12h, 1d)"
        )

    value = int(match.group(1))
    unit = match.group(2)

    return value, unit

def interval_to_seconds(interval_str: str) -> int:
    """Convert a time interval string to seconds.

    Args:
        interval_str: Interval string like "1h", "1d", "1w", "1mo"

    Returns:
        Number of seconds

    Raises:
        ValueError: If the interval string is invalid
    """
    value, unit = parse_interval(interval_str)

    # Convert to seconds
    if unit == "h":
        return value * 3600  # 1 hour = 3600 seconds
    elif unit == "d":
        return value * 86400  # 1 day = 86400 seconds
    elif unit == "w":
        return value * 604800  # 1 week = 604800 seconds
    elif unit == "mo":
        # Approximate 1 month as 30 days
        return value * 2592000  # 30 days = 2592000 seconds
    else:
        raise ValueError(f"Unknown time unit: {unit}")

def parse_time(time_str: str) -> Tuple[int, int]:
    """Parse a time string in 24hr format (HH:MM).

    Args:
        time_str: Time string like "03:00"

    Returns:
        Tuple of (hours, minutes)

    Raises:
        ValueError: If the time string is invalid
    """
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if not match:
        raise ValueError(
            f"Invalid time: {time_str}. Expected format: HH:MM (e.g., 03:00, 15:30)"
        )

    hours = int(match.group(1))
    minutes = int(match.group(2))

    if hours < 0 or hours > 23:
        raise ValueError(f"Invalid hours: {hours}. Expected range: 0-23")

    if minutes < 0 or minutes > 59:
        raise ValueError(f"Invalid minutes: {minutes}. Expected range: 0-59")

    return hours, minutes

def calculate_next_run_time(
    interval: str, start_time: str, now: Optional[datetime] = None
) -> datetime:
    """Calculate the next scheduled run time.

    Args:
        interval: Interval string like "1h", "1d", "1w", "1mo"
        start_time: Start time string like "03:00"
        now: Current time (defaults to now)

    Returns:
        Next run time
    """
    if now is None:
        now = datetime.now()

    # Parse the start time
    start_hours, start_minutes = parse_time(start_time)

    # Get the interval in seconds
    interval_seconds = interval_to_seconds(interval)

    # Create a datetime for today with the start time
    today_start = now.replace(
        hour=start_hours, minute=start_minutes, second=0, microsecond=0
    )

    # If the start time is in the future, use it
    if today_start > now:
        return today_start

    # If the interval is less than a day, add the interval to now
    value, unit = parse_interval(interval)
    if unit == "h" and value < 24:
        # For hourly schedules, just add the interval
        return now + timedelta(seconds=interval_seconds)

    # For daily or longer intervals, use the start time for the next day
    tomorrow_start = today_start + timedelta(days=1)
    return tomorrow_start

def sleep_until(target_time: datetime) -> None:
    """Sleep until the specified time.

    Args:
        target_time: The time to sleep until
    """
    now = datetime.now()
    if target_time <= now:
        logger.warning("Target time is in the past, not sleeping")
        return

    sleep_seconds = (target_time - now).total_seconds()
    logger.info(f"Sleeping until {target_time} ({sleep_seconds:.1f} seconds)")

    while datetime.now() < target_time:
        # Sleep in shorter intervals to allow for interruption
        remaining = (target_time - datetime.now()).total_seconds()
        if remaining <= 0:
            break

        # Sleep for at most 60 seconds at a time
        sleep_time = min(remaining, 60)
        time.sleep(sleep_time)

        # Periodically log the remaining time (in debug mode)
        remaining = (target_time - datetime.now()).total_seconds()
        if remaining > 0:
            logger.debug(f"Sleeping for {remaining:.1f} more seconds until {target_time}")
