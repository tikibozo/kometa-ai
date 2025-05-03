import sys
import os
import signal
import traceback
import argparse
import logging
import time
import json
from typing import List, Dict, Any, Optional, cast
from datetime import datetime

from kometa_ai.__version__ import __version__
from kometa_ai.config import Config
from kometa_ai.utils.logging import setup_logging
from kometa_ai.utils.scheduling import calculate_next_run_time, sleep_until
from kometa_ai.utils.profiling import profiler, profile_time
from kometa_ai.radarr.client import RadarrClient
from kometa_ai.claude.client import ClaudeClient
from kometa_ai.claude.processor import MovieProcessor
from kometa_ai.kometa.parser import KometaParser
# Add type stubs for mypy to avoid import-not-found error
import sys
from typing import Dict, List, Any, Optional, Type, Protocol, cast

# Define protocol class for type checking
class IStateManager(Protocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def load(self) -> None: ...
    def save(self) -> None: ...
    def log_change(self, *args: Any, **kwargs: Any) -> None: ...
    def log_error(self, *args: Any, **kwargs: Any) -> None: ...
    def get_changes(self) -> List[Dict[str, Any]]: ...
    def get_errors(self) -> List[Dict[str, Any]]: ...
    def reset(self) -> None: ...
    def dump(self) -> str: ...

# Import or define StateManager
if not sys.modules.get('kometa_ai.state.manager'):
    # Create a module object to avoid import errors
    class _StateManager:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass
        def load(self) -> None:
            pass
        def save(self) -> None:
            pass
        def log_change(self, *args: Any, **kwargs: Any) -> None:
            pass
        def log_error(self, *args: Any, **kwargs: Any) -> None:
            pass
        def get_changes(self) -> List[Dict[str, Any]]:
            return []
        def get_errors(self) -> List[Dict[str, Any]]:
            return []
        def reset(self) -> None:
            pass
        def dump(self) -> str:
            return "{}"
    
    # Use the mock class
    StateManager: Type[IStateManager] = _StateManager
else:
    # Import the real class if available
    from kometa_ai.state.manager import StateManager  # type: ignore
from kometa_ai.tag_manager import TagManager
from kometa_ai.notification.email import EmailNotifier
from kometa_ai.notification.formatter import NotificationFormatter


# Global flag for handling termination signals
terminate_requested = False


def signal_handler(sig, frame):
    """Handle termination signals by setting a global flag."""
    global terminate_requested
    logging.getLogger(__name__).warning(
        f"Received signal {sig}, preparing for graceful shutdown")
    terminate_requested = True


def setup_signal_handlers():
    """Set up signal handlers for graceful termination."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Windows doesn't support SIGUSR1, etc.
    try:
        signal.signal(signal.SIGUSR1, signal_handler)
    except AttributeError:
        pass


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kometa-AI: Claude integration for Radarr collections")

    parser.add_argument("--run-now", action="store_true",
                        help="Run immediately instead of waiting for schedule")
    parser.add_argument("--dry-run", action="store_true",
                        help=("Perform all operations without making actual "
                              "changes"))
    parser.add_argument("--collection", type=str,
                        help="Process only the specified collection")
    parser.add_argument("--batch-size", type=int,
                        help="Override default batch size")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Reprocess all movies, ignoring cached decisions")
    parser.add_argument("--health-check", action="store_true",
                        help="Run internal health check and exit")
    parser.add_argument("--dump-config", action="store_true",
                        help="Print current configuration and exit")
    parser.add_argument("--dump-state", action="store_true",
                        help="Print current state file and exit")
    parser.add_argument("--reset-state", action="store_true",
                        help="Clear state file and start fresh")
    parser.add_argument("--send-test-email", action="store_true",
                        help="Send a test email and exit")
    parser.add_argument("--version", action="store_true",
                        help="Show version information and exit")

    # Performance profiling options
    performance_group = parser.add_argument_group('Performance Options')
    performance_group.add_argument("--profile", action="store_true",
                                   help="Enable performance profiling")
    performance_group.add_argument(
        "--profile-output", type=str,
        help=("File to save profiling data "
              "(default: profile_results.json)"))
    performance_group.add_argument(
        "--optimize-batch-size", action="store_true",
        help="Run batch size optimization test")
    performance_group.add_argument(
        "--memory-profile", action="store_true",
        help="Run with detailed memory profiling")

    return parser.parse_args(args)


def run_health_check() -> bool:
    """Run health check with Radarr and Claude connectivity tests.

    Returns:
        True if healthy, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        # Check required environment variables
        radarr_url = Config.get("RADARR_URL")
        radarr_api_key = Config.get("RADARR_API_KEY")
        claude_api_key = Config.get("CLAUDE_API_KEY")

        if not all([radarr_url, radarr_api_key, claude_api_key]):
            logger.error("Missing required API configuration")
            return False

        # Check Radarr connectivity
        logger.info("Checking Radarr connectivity...")
        radarr_client = RadarrClient(radarr_url, radarr_api_key)
        if not radarr_client.test_connection():
            logger.error("Failed to connect to Radarr API")
            return False
        logger.info("Successfully connected to Radarr API")

        # Check Claude connectivity
        logger.info("Checking Claude API connectivity...")
        claude_client = ClaudeClient(claude_api_key)
        if not claude_client.test_connection():
            logger.error("Failed to connect to Claude API")
            return False
        logger.info("Successfully connected to Claude API")

        # Check Kometa configuration
        logger.info("Checking Kometa configuration...")
        kometa_config_dir = os.path.join(os.getcwd(), "kometa-config")
        if not os.path.exists(kometa_config_dir):
            logger.error(
                f"Kometa configuration directory not found: "
                f"{kometa_config_dir}")
            return False
        logger.info("Kometa configuration directory exists")

        # Check state directory
        logger.info("Checking state directory...")
        state_dir = os.path.join(os.getcwd(), "state")
        os.makedirs(state_dir, exist_ok=True)
        logger.info("State directory exists or was created")

        # Check for email configuration (optional)
        logger.info("Checking email configuration...")
        smtp_server = Config.get("SMTP_SERVER", "")
        if not smtp_server:
            logger.warning(
                "SMTP_SERVER not configured, email notifications will be disabled")
        else:
            logger.info("Email configuration found")

        # Check schedule configuration
        logger.info("Checking schedule configuration...")
        schedule_interval = Config.get("SCHEDULE_INTERVAL", "")
        schedule_start_time = Config.get("SCHEDULE_START_TIME", "")

        if not schedule_interval:
            logger.warning(
                "SCHEDULE_INTERVAL not configured, defaulting to 1d")

        if not schedule_start_time:
            logger.warning(
                "SCHEDULE_START_TIME not configured, defaulting to 03:00")

        if schedule_interval and schedule_start_time:
            logger.info(
                f"Schedule configured: every {schedule_interval} "
                f"starting at {schedule_start_time}")

        logger.info("All health checks completed successfully")
        return True
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return False


@profile_time
def process_collections(
    radarr_client: RadarrClient,
    claude_client: ClaudeClient,
    state_manager: StateManager,
    collections: List[Any],
    dry_run: bool = False,
    batch_size: Optional[int] = None,
    force_refresh: bool = False,
    enable_profiling: bool = False
) -> Dict[str, Any]:
    """Process all collections and apply tag changes.

    Args:
        radarr_client: Radarr API client
        claude_client: Claude API client
        state_manager: State manager for persistence
        collections: List of collections to process
        dry_run: If True, don't apply changes
        batch_size: Override default batch size
        force_refresh: Force reprocessing of all movies
        enable_profiling: Enable detailed performance profiling

    Returns:
        Dictionary with processing results and statistics
    """
    logger = logging.getLogger(__name__)

    # Start profiling if enabled
    if enable_profiling:
        profiler.start()

    # Fetch movies once to minimize API calls
    logger.info("Fetching movies from Radarr")
    all_movies = radarr_client.get_movies()
    logger.info(f"Retrieved {len(all_movies)} movies from Radarr")

    # Create tag manager
    tag_manager = TagManager(radarr_client)

    # Create movie processor
    processor = MovieProcessor(
        claude_client=claude_client,
        state_manager=state_manager,
        batch_size=batch_size,
        force_refresh=force_refresh
    )

    # Track overall statistics
    results: Dict[str, Any] = {
        "total_changes": 0,
        "collections_processed": 0,
        "movies_processed": 0,
        "errors": [],
        "changes": [],
        "collection_stats": {}
    }

    # Process each collection
    for collection in collections:
        if not collection.enabled:
            logger.info(
                f"Collection '{collection.name}' is disabled, skipping")
            continue

        if terminate_requested:
            logger.warning(
                "Termination requested, stopping collection processing")
            break

        logger.info(
            f"Processing collection '{collection.name}'...")

        try:
            # Mark collection start for profiling
            if enable_profiling:
                profiler.mark_collection_start(collection.name)

            # Classify movies for this collection
            logger.info(
                f"Classifying movies for '{collection.name}' "
                f"with Claude AI...")
            included_ids, excluded_ids, stats = processor.process_collection(
                collection=collection,
                movies=all_movies
            )
            logger.info(
                f"Classification complete: {len(included_ids)} movies included, "
                f"{len(excluded_ids)} excluded")

            # Apply tag changes
            if not dry_run:
                logger.info(
                    f"Applying tag changes for collection '{collection.name}'...")
                changes = tag_manager.reconcile_collection_membership(
                    collection_name=collection.name,
                    tag=collection.tag,
                    included_movie_ids=included_ids,
                    all_movies=all_movies
                )

                for change in changes:
                    # Log the change in state for notification
                    movie_id = change["movie_id"]
                    movie = next(
                        (m for m in all_movies if m.id == movie_id), None)
                    movie_title = movie.title if movie else f"Movie {movie_id}"

                    state_manager.log_change(
                        movie_id=movie_id,
                        movie_title=movie_title,
                        collection_name=collection.name,
                        action=change["action"],
                        tag=collection.tag
                    )

                if changes:
                    added = len([c for c in changes if c["action"] == "added"])
                    removed = len([c for c in changes if c["action"] == "removed"])
                    logger.info(
                        f"Applied {len(changes)} tag changes for '{collection.name}': "
                        f"{added} added, {removed} removed")
                else:
                    logger.info(
                        f"No changes needed for collection '{collection.name}'")

                results["total_changes"] = cast(int, results["total_changes"]) + len(changes)
                cast(list, results["changes"]).extend(changes)
            else:
                logger.info(
                    f"Dry run mode: would apply {len(included_ids)} tag changes "
                    f"for '{collection.name}'")

            # Store statistics
            cast(Dict[str, Any], results["collection_stats"])[collection.name] = stats
            results["collections_processed"] = cast(int, results["collections_processed"]) + 1
            results["movies_processed"] = cast(int, results["movies_processed"]) + stats.get("processed_movies", 0)

            # Mark collection end for profiling
            if enable_profiling:
                profiler.mark_collection_end(collection.name, stats)

        except Exception as e:
            error_msg = (
                f"Error processing collection '{collection.name}': {str(e)}"
            )
            logger.error(f"{error_msg}")

            # Log error in state for notification
            state_manager.log_error(
                context=f"collection:{collection.name}",
                error_message=str(e)
            )

            # Add to results for summary
            cast(list, results["errors"]).append({
                "collection": collection.name,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

    # Save state with all changes and errors
    state_manager.save()

    # Stop profiling if enabled and store the results
    if enable_profiling:
        profiling_results = profiler.stop()
        results["profiling"] = profiling_results

    # Generate summary with more details
    error_count = len(results['errors'])
    if error_count > 0:
        error_status = f" with {error_count} errors"
    else:
        error_status = " with no errors"

    if cast(int, results['total_changes']) > 0:
        logger.info(
            f"Completed: Processed {results['collections_processed']} collections "
            f"with {results['total_changes']} changes{error_status}")
    else:
        logger.info(
            f"Completed: Processed {results['collections_processed']} collections "
            f"with no changes{error_status}")

    return results


def send_notifications(
    results: Dict[str, Any],
    state_manager: StateManager,
    next_run_time: Optional[datetime] = None
) -> bool:
    """Send email notifications about processing results.

    Args:
        results: Processing results
        state_manager: State manager (for change/error history)
        next_run_time: Next scheduled run time

    Returns:
        True if notification was sent, False otherwise
    """
    logger = logging.getLogger(__name__)

    # Create email notifier
    email_notifier = EmailNotifier()

    if not email_notifier.can_send():
        logger.warning("Email notifications not configured, skipping")
        return False

    # Get changes and errors from state for notification
    logger.info("Preparing email notification...")
    recent_changes = state_manager.get_changes()
    recent_errors = state_manager.get_errors()

    # Determine if notification should be sent
    has_changes = len(recent_changes) > 0
    has_errors = len(recent_errors) > 0

    if not email_notifier.should_send(
            has_changes=has_changes, has_errors=has_errors):
        logger.info("No changes or errors to report, skipping notification")
        return False

    logger.info(
        f"Found {len(recent_changes)} changes and {len(recent_errors)} errors to report")

    # Format email content
    subject = (
        f"Kometa-AI Processing Report: {len(recent_changes)} changes, "
        f"{len(recent_errors)} errors"
    )

    message = NotificationFormatter.format_summary(
        changes=recent_changes,
        errors=recent_errors,
        next_run_time=next_run_time,
        collection_stats=results.get("collection_stats", {}),
        version=__version__
    )

    # Send notification
    recipients_str = ", ".join(email_notifier.recipients)
    logger.info(f"Sending notification email to {recipients_str}...")

    sent = email_notifier.send_notification(subject=subject, message=message)

    if sent:
        logger.info("Notification email sent successfully")
    else:
        logger.error("Failed to send notification email")

    return sent


def calculate_schedule() -> datetime:
    """Calculate the next scheduled run time based on configuration.

    Returns:
        Datetime of the next scheduled run
    """
    logger = logging.getLogger(__name__)

    # Get schedule configuration
    interval = Config.get("SCHEDULE_INTERVAL", "1d")
    start_time = Config.get("SCHEDULE_START_TIME", "03:00")

    logger.info(
        f"Calculating schedule with interval={interval}, start_time={start_time}")

    # Calculate next run time
    next_run = calculate_next_run_time(interval, start_time)

    # Format date for display
    formatted_date = next_run.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Next scheduled run: {formatted_date}")
    return next_run


@profile_time
def run_scheduled_pipeline(args: argparse.Namespace) -> int:
    """Run the core processing pipeline with scheduling.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    logger = logging.getLogger(__name__)

    try:
        # Initialize resources
        state_dir = os.path.join(os.getcwd(), "state")
        kometa_config_dir = os.path.join(os.getcwd(), "kometa-config")
        state_manager = StateManager(state_dir)
        state_manager.load()

        # Get API configurations
        radarr_url = Config.get("RADARR_URL")
        radarr_api_key = Config.get("RADARR_API_KEY")
        claude_api_key = Config.get("CLAUDE_API_KEY")

        if not all([radarr_url, radarr_api_key, claude_api_key]):
            logger.error("Missing required API configuration")
            return 1

        # Create clients with retry for Radarr
        logger.info(f"Initializing Radarr client (URL: {radarr_url})...")
        max_attempts = 10  # More retries for container startup
        attempt = 0

        # Calculate exponential backoff times with jitter
        backoff_times = [min(2 ** i + (i * 0.1), 60)
                         for i in range(max_attempts)]

        while attempt < max_attempts:
            attempt += 1
            backoff = backoff_times[attempt - 1]

            try:
                radarr_client = RadarrClient(
                    radarr_url, radarr_api_key, max_retries=3)
                if radarr_client.test_connection():
                    logger.info(
                        f"Successfully connected to Radarr at {radarr_url}")
                    break
                else:
                    logger.warning(
                        f"Radarr connection test failed "
                        f"(attempt {attempt}/{max_attempts}), "
                        f"retrying in {backoff:.2f}s...")
                    time.sleep(backoff)
            except Exception as e:
                if attempt >= max_attempts:
                    logger.error(
                        f"Failed to connect to Radarr at {radarr_url} after "
                        f"{max_attempts} attempts")
                    logger.error(f"Last error: {str(e)}")
                    raise

                logger.warning(
                    f"Error initializing Radarr client (attempt {attempt}/{max_attempts}): "
                    f"{str(e)}")
                logger.warning(f"Retrying in {backoff:.2f}s...")
                time.sleep(backoff)

        logger.info("Initializing Claude client...")
        claude_client = ClaudeClient(
            claude_api_key, debug_mode=Config.get_bool("DEBUG_LOGGING", False))

        # Parse Kometa configuration
        logger.info("Loading collection configurations...")
        kometa_parser = KometaParser(kometa_config_dir)
        all_collections = kometa_parser.parse_configs()

        # Filter collections if --collection argument is provided
        if args.collection:
            logger.info(f"Filtering for collection: '{args.collection}'")
            collections = [
                c for c in all_collections
                if c.name.lower() == args.collection.lower()
            ]
            if not collections:
                logger.error(
                    f"Collection '{args.collection}' not found or not enabled")
                return 1
            logger.info(
                f"Found collection '{args.collection}'")
        else:
            collections = all_collections

        logger.info(
            f"Found {len(collections)} collections to process")

        # Set up batch size optimization test if requested
        if args.optimize_batch_size:
            logger.info(
                "Starting batch size optimization test")
            return run_batch_size_optimization(
                radarr_client=radarr_client,
                claude_client=claude_client,
                state_manager=state_manager,
                collections=collections,
                output_file=(
                    args.profile_output or "batch_size_optimization.json"
                )
            )

        # Calculate next run time if not in run-now mode
        if not args.run_now:
            next_run_time = calculate_schedule()

            # Sleep until next run time
            formatted_time = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"Entering scheduled mode, waiting until {formatted_time}")
            sleep_until(next_run_time)

            if terminate_requested:
                logger.info(
                    "Termination requested during schedule wait, exiting")
                return 0

        # Run the main pipeline
        while not terminate_requested:
            run_start_time = datetime.now()
            formatted_start = run_start_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"Starting processing run at {formatted_start}")

            # Process collections with profiling if enabled
            results = process_collections(
                radarr_client=radarr_client,
                claude_client=claude_client,
                state_manager=state_manager,
                collections=collections,
                dry_run=args.dry_run,
                batch_size=args.batch_size,
                force_refresh=args.force_refresh,
                enable_profiling=args.profile or args.memory_profile
            )

            # Save profiling results if enabled
            if args.profile and "profiling" in results:
                profile_output = args.profile_output or "profile_results.json"
                logger.info(f"Saving profiling results to {profile_output}")

                try:
                    with open(profile_output, 'w') as f:
                        json.dump(results["profiling"], f, indent=2)
                    logger.info(f"Profiling results saved to {profile_output}")
                except Exception as e:
                    logger.error(f"Error saving profiling results: {e}")

            # Calculate next run time for notification
            notification_run_time: Optional[datetime] = None
            if not args.run_now:
                notification_run_time = calculate_schedule()

            # Send notifications
            send_notifications(
                results=results,
                state_manager=state_manager,
                next_run_time=notification_run_time
            )

            # Exit if run-now mode or termination requested
            if args.run_now or terminate_requested:
                logger.info(
                    "Single run completed, exiting")
                break

            # Sleep until next run
            next_run_time = calculate_schedule()
            formatted_next = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(
                f"Run completed, waiting until next scheduled run at "
                f"{formatted_next}")
            sleep_until(next_run_time)

            if terminate_requested:
                logger.info(
                    "Termination requested during schedule wait, exiting")
                break

        return 0

    except Exception as e:
        logger.error(
            f"Error in main pipeline: {str(e)}")
        logger.error(traceback.format_exc())

        # Try to send error notification
        try:
            email_notifier = EmailNotifier()
            if email_notifier.can_send():
                subject = "Kometa-AI Critical Error"
                message = NotificationFormatter.format_error_notification(
                    error_context="main_pipeline",
                    error_message=str(e),
                    traceback=traceback.format_exc(),
                    version=__version__
                )
                email_notifier.send_notification(subject, message)
        except Exception as notify_error:
            logger.error(
                f"Failed to send error notification: {str(notify_error)}")

        return 1


def run_batch_size_optimization(
    radarr_client: RadarrClient,
    claude_client: ClaudeClient,
    state_manager: StateManager,
    collections: List[Any],
    output_file: str = "batch_size_optimization.json"
) -> int:
    """Run batch size optimization test.

    This test runs the same collection processing with different batch sizes
    to determine the optimal size for performance and cost.

    Args:
        radarr_client: Radarr API client
        claude_client: Claude API client
        state_manager: State manager
        collections: List of collections to test
        output_file: File to save results

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    logger = logging.getLogger(__name__)

    # Fetch all movies once
    logger.info("Fetching movies from Radarr for batch size testing")
    all_movies = radarr_client.get_movies()
    logger.info(f"Retrieved {len(all_movies)} movies")

    # Select a single collection for testing
    if not collections:
        logger.error("No collections found for testing")
        return 1

    test_collection = collections[0]
    logger.info(
        f"Using collection '{test_collection.name}' for batch size testing")

    # Define batch sizes to test
    batch_sizes = [50, 100, 150, 200, 250, 300]

    # Store results
    results = {
        "collection": test_collection.name,
        "movie_count": len(all_movies),
        "timestamp": datetime.now().isoformat(),
        "batch_results": {}
    }

    # Test each batch size
    for batch_size in batch_sizes:
        logger.info(f"Testing batch size: {batch_size}")

        # Reset clients to ensure clean testing
        claude_client.reset_usage_stats()
        profiler.start()

        start_time = time.time()

        # Process with this batch size
        processor = MovieProcessor(
            claude_client=claude_client,
            state_manager=state_manager,
            batch_size=batch_size,
            force_refresh=True
        )

        included_ids, excluded_ids, stats = processor.process_collection(
            collection=test_collection,
            movies=all_movies
        )

        duration = time.time() - start_time
        profiling_data = profiler.stop()

        # Store batch results
        results["batch_results"][str(batch_size)] = {
            "duration": duration,
            "included_count": len(included_ids),
            "excluded_count": len(excluded_ids),
            "claude_usage": claude_client.get_usage_stats(),
            "profiling": profiling_data,
            "cost_per_movie": (
                stats.get("total_cost", 0) / len(all_movies)
                if len(all_movies) > 0 else 0
            )
        }

        logger.info(
            f"Batch size {batch_size} completed in {duration:.2f}s - "
            f"Token usage: {stats.get('total_input_tokens', 0)} input, "
            f"{stats.get('total_output_tokens', 0)} output")

        # Wait a bit between tests to avoid rate limits
        time.sleep(2)

    # Calculate optimal batch size based on cost and speed
    optimal_size = None
    best_efficiency = 0

    for size, data in results["batch_results"].items():
        # Calculate efficiency as movies processed per second per dollar
        if data["duration"] > 0 and data["claude_usage"]["total_cost"] > 0:
            movies_per_second = len(all_movies) / data["duration"]
            cost_efficiency = (
                movies_per_second / data["claude_usage"]["total_cost"])
            data["efficiency"] = cost_efficiency

            if cost_efficiency > best_efficiency:
                best_efficiency = cost_efficiency
                optimal_size = int(size)

    results["optimal_batch_size"] = optimal_size

    # Save results
    try:
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Batch size optimization results saved to {output_file}")
    except Exception as e:
        logger.error(f"Error saving optimization results: {e}")

    logger.info(f"Optimal batch size determined to be {optimal_size}")
    return 0


def send_test_email() -> bool:
    """Send a test email to verify email configuration.

    Returns:
        True if sent successfully, False otherwise
    """
    logger = logging.getLogger(__name__)

    try:
        email_notifier = EmailNotifier()

        if not email_notifier.can_send():
            logger.error("Email configuration is incomplete, cannot send test")
            return False

        subject = "Kometa-AI Test Email"
        message = f"""# Kometa-AI Test Email

This is a test email from Kometa-AI v{__version__}
to verify your email configuration.

## Configuration
- SMTP Server: {email_notifier.smtp_server}
- SMTP Port: {email_notifier.smtp_port}
- From Address: {email_notifier.from_address}
- To: {", ".join(email_notifier.recipients)}
- SSL: {'Enabled' if email_notifier.use_ssl else 'Disabled'}
- TLS: {'Enabled' if email_notifier.use_tls else 'Disabled'}
- Authentication: {'Enabled' if email_notifier.smtp_username else 'Disabled'}

If you're seeing this email, your email configuration is working correctly!
"""

        sent = email_notifier.send_notification(subject, message)

        if sent:
            logger.info("Test email sent successfully")
        else:
            logger.error("Failed to send test email")

        return sent

    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        return False


def main(args: Optional[List[str]] = None) -> int:
    # Parse arguments
    parsed_args = parse_args(args)

    # Setup signal handlers
    setup_signal_handlers()

    # Show version if requested
    if parsed_args.version:
        print(f"Kometa-AI version {__version__}")
        return 0

    # Setup logging
    debug_mode = (parsed_args.dump_config or parsed_args.dump_state or
                  Config.get_bool("DEBUG_LOGGING", False))
    setup_logging(debug=debug_mode)
    logger = logging.getLogger(__name__)

    logger.info(f"Starting Kometa-AI v{__version__}")

    # Run health check if requested
    if parsed_args.health_check:
        is_healthy = run_health_check()
        logger.info(f"Health check: {'Passed' if is_healthy else 'Failed'}")
        return 0 if is_healthy else 1

    # Dump configuration if requested
    if parsed_args.dump_config:
        Config().dump()
        return 0

    # State management
    state_dir = os.path.join(os.getcwd(), "state")
    state_manager = StateManager(state_dir)

    # Dump state if requested
    if parsed_args.dump_state:
        try:
            state_manager.load()
            print(state_manager.dump())
        except Exception as e:
            logger.error(f"Error loading state: {str(e)}")
            return 1
        return 0

    # Reset state if requested
    if parsed_args.reset_state:
        try:
            state_manager.reset()
            logger.info("State reset successfully")
        except Exception as e:
            logger.error(f"Error resetting state: {str(e)}")
            return 1
        return 0

    # Send test email if requested
    if parsed_args.send_test_email:
        success = send_test_email()
        return 0 if success else 1

    # Run the main pipeline
    return run_scheduled_pipeline(parsed_args)


if __name__ == "__main__":
    sys.exit(main())
