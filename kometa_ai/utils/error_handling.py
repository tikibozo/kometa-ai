"""
Error handling utilities for Kometa-AI.

This module provides tools for handling errors, implementing resilient
retry mechanisms, and recovering from failure states.
"""

import logging
import time
import sys
import random
import traceback
from typing import Callable, TypeVar, Any, Dict, Optional, List, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

# Type variable for generic function
T = TypeVar('T')

# Error classification and categorization
class ErrorCategory:
    """Categorization of errors for appropriate handling."""
    TRANSIENT = "transient"  # Network, temporary API issues
    RESOURCE = "resource"    # Memory, disk space, etc.
    VALIDATION = "validation" # Format issues, schema problems
    CONFIGURATION = "configuration" # Missing config, wrong settings
    CRITICAL = "critical"    # Severe errors requiring human intervention
    UNKNOWN = "unknown"      # Unclassified errors


class ErrorContext:
    """Context for error tracking and handling."""
    
    def __init__(
        self, 
        context: str,
        error: Exception, 
        category: str = ErrorCategory.UNKNOWN, 
        retry_count: int = 0,
        traceback_str: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """Initialize error context.
        
        Args:
            context: Context where the error occurred (e.g., collection name, operation)
            error: The exception object
            category: Error category for appropriate handling
            retry_count: Number of retries already attempted
            traceback_str: Formatted traceback string (generated if None)
            additional_info: Additional debugging information
        """
        self.context = context
        self.error = error
        self.category = category
        self.retry_count = retry_count
        self.traceback_str = traceback_str or "".join(traceback.format_exception(
            type(error), error, error.__traceback__
        ))
        self.additional_info = additional_info or {}
        self.timestamp = time.time()
    
    def __str__(self) -> str:
        """String representation of the error context."""
        return (f"Error in '{self.context}' ({self.category}): {str(self.error)} "
                f"[Retry count: {self.retry_count}]")


def categorize_error(error: Exception) -> str:
    """Categorize an error for appropriate handling.
    
    Args:
        error: The exception to categorize
        
    Returns:
        Error category
    """
    error_type = type(error).__name__
    error_str = str(error).lower()
    
    # Network and API errors
    if any(x in error_type for x in ["Timeout", "ConnectionError", "HTTPError"]):
        return ErrorCategory.TRANSIENT
    
    # Resource exhaustion
    if any(x in error_str for x in ["memory", "disk space", "quota", "limit exceeded"]):
        return ErrorCategory.RESOURCE
    
    # Configuration issues
    if any(x in error_str for x in ["config", "missing key", "environment variable"]):
        return ErrorCategory.CONFIGURATION
    
    # Validation errors
    if any(x in error_str for x in ["invalid", "schema", "format", "parse"]):
        return ErrorCategory.VALIDATION
    
    # Critical errors requiring attention
    if any(x in error_str for x in ["permission denied", "authentication", "not authorized"]):
        return ErrorCategory.CRITICAL
    
    return ErrorCategory.UNKNOWN


def retry_with_backoff(
    max_retries: int = 5, 
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_categories: Optional[List[str]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        retryable_categories: List of error categories that are retryable
        
    Returns:
        Decorated function with retry logic
    """
    if retryable_categories is None:
        retryable_categories = [ErrorCategory.TRANSIENT, ErrorCategory.RESOURCE]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    
                    # Categorize the error
                    category = categorize_error(e)
                    
                    # Create error context
                    error_ctx = ErrorContext(
                        context=func.__name__,
                        error=e,
                        category=category,
                        retry_count=retries
                    )
                    
                    # Check if we should retry
                    if category not in retryable_categories:
                        logger.error(f"Non-retryable error: {error_ctx}")
                        raise
                    
                    if retries > max_retries:
                        logger.error(f"Exceeded maximum retries ({max_retries}): {error_ctx}")
                        raise
                    
                    # Calculate backoff with jitter (±10%)
                    delay = min(base_delay * (2 ** (retries - 1)), max_delay)
                    jitter = delay * 0.1 * (2 * random.random() - 1)
                    delay_with_jitter = delay + jitter
                    
                    logger.warning(
                        f"Retrying ({retries}/{max_retries}) after error: {str(e)} - "
                        f"Waiting {delay_with_jitter:.2f}s"
                    )
                    
                    time.sleep(delay_with_jitter)
        
        return wrapper
    
    return decorator


def handle_error(
    error: Exception, 
    context: str,
    state_manager: Optional[Any] = None,
    should_retry: bool = True,
    max_retries: int = 3
) -> Tuple[bool, ErrorContext]:
    """Handle an error with appropriate logging and recovery.
    
    Args:
        error: The exception to handle
        context: Context where the error occurred
        state_manager: Optional state manager for error logging
        should_retry: Whether to recommend retrying the operation
        max_retries: Maximum number of retries to recommend
        
    Returns:
        Tuple of (should_retry, error_context)
    """
    # Categorize the error
    category = categorize_error(error)
    
    # Create error context
    error_ctx = ErrorContext(
        context=context,
        error=error,
        category=category
    )
    
    # Log the error
    logger.error(f"Error in {context}: {str(error)}")
    logger.debug(f"Error details: {error_ctx.traceback_str}")
    
    # Log in state manager if available
    if state_manager is not None and hasattr(state_manager, 'log_error'):
        state_manager.log_error(
            context=context,
            error_message=str(error)
        )
    
    # Determine if we should retry based on category
    should_retry_after_error = should_retry and category in [
        ErrorCategory.TRANSIENT, ErrorCategory.RESOURCE
    ]
    
    return should_retry_after_error, error_ctx


class ErrorRecoveryTask:
    """Task for recovering from errors."""
    
    def __init__(
        self, 
        name: str,
        recovery_function: Callable,
        error_context: ErrorContext,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """Initialize recovery task.
        
        Args:
            name: Name of the recovery task
            recovery_function: Function to call for recovery
            error_context: Context of the error to recover from
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
        """
        self.name = name
        self.recovery_function = recovery_function
        self.error_context = error_context
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.retry_count = 0
        self.success = False
    
    def execute(self) -> bool:
        """Execute the recovery task.
        
        Returns:
            True if recovery was successful, False otherwise
        """
        if self.retry_count >= self.max_retries:
            logger.error(f"Recovery task '{self.name}' exceeded maximum retries")
            return False
        
        try:
            logger.info(f"Executing recovery task '{self.name}' (attempt {self.retry_count + 1}/{self.max_retries})")
            self.recovery_function(self.error_context)
            self.success = True
            logger.info(f"Recovery task '{self.name}' completed successfully")
            return True
        except Exception as e:
            self.retry_count += 1
            logger.warning(
                f"Recovery task '{self.name}' failed: {str(e)}. "
                f"Retrying in {self.retry_delay}s ({self.retry_count}/{self.max_retries})"
            )
            time.sleep(self.retry_delay)
            return False


# Common recovery strategies
def recover_from_memory_error(error_ctx: ErrorContext) -> None:
    """Recover from memory exhaustion errors.
    
    Args:
        error_ctx: Error context
    """
    import gc
    
    logger.info("Attempting to recover from memory error by forcing garbage collection")
    gc.collect()
    
    # Log available memory
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        logger.info(f"Current memory usage: {memory_info.rss / (1024 * 1024):.2f} MB")
    except ImportError:
        pass


def recover_from_state_corruption(error_ctx: ErrorContext) -> None:
    """Recover from state corruption errors.
    
    Args:
        error_ctx: Error context
    """
    state_manager = error_ctx.additional_info.get('state_manager')
    if state_manager is None:
        logger.error("Cannot recover from state corruption: no state manager provided")
        return
    
    logger.info("Attempting to recover from state corruption by restoring from backup")
    state_manager._try_restore_backup()


def recover_from_api_error(error_ctx: ErrorContext) -> None:
    """Recover from API errors.
    
    Args:
        error_ctx: Error context
    """
    # Simply wait to recover from rate limiting or temporary API issues
    logger.info("Waiting to recover from API error")
    time.sleep(10.0)  # Wait longer for API to recover