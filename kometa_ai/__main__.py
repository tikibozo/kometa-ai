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
from kometa_ai.utils.run_lock import acquire_run_lock
from kometa_ai.utils.scheduling import calculate_next_run_time, sleep_until
from kometa_ai.radarr.client import RadarrClient
from kometa_ai.claude.client import ClaudeBackend, ClaudeClient
from kometa_ai.claude.cli_client import ClaudeCliClient
from kometa_ai.claude.processor import MovieProcessor
from kometa_ai.kometa.parser import KometaParser
from kometa_ai.state.manager import StateManager
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


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kometa-AI: Claude integration for Radarr collections")

    parser.add_argument("--run-now", action="store_true",
                        help="Run immediately for the first execution, then switch to scheduled mode")
    parser.add_argument("--dry-run", action="store_true",
                        help=("Perform all operations without making actual "
                              "changes"))
    parser.add_argument("--collection", type=str,
                        help="Process only the specified collection")
    parser.add_argument("--batch-size", type=int,
                        help="Override default batch size")
    parser.add_argument("--force-refresh", action="store_true",
                        help="Reprocess all movies, ignoring cached decisions")
    parser.add_argument("--max-evals", type=int, default=None,
                        help=("Cap movies sent to Claude per run across all "
                              "collections (overrides MAX_EVALS_PER_RUN; 0 = no cap)"))
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

        if not all([radarr_url, radarr_api_key]):
            logger.error("Missing required API configuration")
            return False

        # Check Claude backend configuration (same rules the pipeline uses)
        if make_claude_client() is None:
            return False

        # Check Radarr connectivity
        logger.info("Checking Radarr connectivity...")
        radarr_client = RadarrClient(radarr_url, radarr_api_key)
        if not radarr_client.test_connection():
            logger.error("Failed to connect to Radarr API")
            return False
        logger.info("Successfully connected to Radarr API")


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


def make_claude_client() -> Optional[ClaudeBackend]:
    """Build the configured Claude backend (API key or CLI/subscription).

    Returns:
        A client exposing classify_movies/get_usage_stats/reset_usage_stats,
        or None if the backend is misconfigured.
    """
    logger = logging.getLogger(__name__)
    backend = Config.get("CLAUDE_BACKEND", "api").lower()
    debug_mode = Config.get_bool("DEBUG_LOGGING", False)
    model = Config.get("CLAUDE_MODEL")

    if backend == "cli":
        import shutil
        if not shutil.which("claude"):
            logger.error("CLAUDE_BACKEND=cli but the claude CLI is not on PATH")
            return None
        logger.info("Using Claude CLI backend (subscription billing)")
        return ClaudeCliClient(debug_mode=debug_mode, model=model)

    if backend != "api":
        logger.error(f"Unknown CLAUDE_BACKEND '{backend}' (expected 'api' or 'cli')")
        return None

    api_key = Config.get("CLAUDE_API_KEY")
    if not api_key:
        logger.error("CLAUDE_API_KEY is required with CLAUDE_BACKEND=api")
        return None
    return ClaudeClient(api_key, debug_mode=debug_mode, model=model)


def process_collections(
    radarr_client: RadarrClient,
    claude_client: ClaudeBackend,
    state_manager: StateManager,
    collections: List[Any],
    all_movies: Optional[List[Any]] = None,
    dry_run: bool = False,
    batch_size: Optional[int] = None,
    force_refresh: bool = False,
    max_evals_per_run: Optional[int] = None
) -> Dict[str, Any]:
    """Process all collections and apply tag changes.

    Args:
        radarr_client: Radarr API client
        claude_client: Claude API client
        state_manager: State manager for persistence
        collections: List of collections to process
        all_movies: Optional list of movies already fetched from Radarr
        dry_run: If True, don't apply changes
        batch_size: Override default batch size
        force_refresh: Force reprocessing of all movies
        max_evals_per_run: Soft cap on movies sent to Claude across all
            collections this run (Lever 2); None/0 = no cap

    Returns:
        Dictionary with processing results and statistics
    """
    logger = logging.getLogger(__name__)

    # Use provided movies or fetch them if not provided
    if all_movies is None:
        # Fetch movies once to minimize API calls
        logger.info("Fetching movies from Radarr")
        all_movies = radarr_client.get_movies()
        logger.info(f"Retrieved {len(all_movies)} movies from Radarr")
    else:
        logger.info(f"Using {len(all_movies)} movies already fetched from Radarr")

    # Create tag manager
    tag_manager = TagManager(radarr_client)

    # Create movie processor
    processor = MovieProcessor(
        claude_client=claude_client,
        state_manager=state_manager,
        batch_size=batch_size,
        force_refresh=force_refresh,
        max_evals_per_run=max_evals_per_run
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
                # Pass no snapshot: reconcile refetches current tag state from
                # Radarr so the diff reflects reality at write time, not the
                # (possibly stale) start-of-run snapshot.
                changes = tag_manager.reconcile_collection_membership(
                    collection_name=collection.name,
                    tag=collection.tag,
                    included_movie_ids=included_ids,
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

        # A usage limit stops the whole run: the remaining collections would
        # only hit the same limit. Decided movies are already tagged and
        # checkpointed, so they resume on the next scheduled run.
        if processor.usage_limited:
            logger.warning(
                "Stopping run early — Claude usage limit reached. Remaining "
                "collections and movies will resume on the next scheduled run."
            )
            break

    # Save state with all changes and errors
    state_manager.save()

    # Surface any budget deferrals so a paced backfill isn't mistaken for a
    # silent cap — the deferred movies resume on the next run.
    total_deferred = sum(
        s.get('deferred', 0) for s in cast(Dict[str, Any], results['collection_stats']).values()
    )
    if total_deferred:
        logger.info(
            f"{total_deferred} movies deferred by the per-run evaluation budget; "
            f"they will be processed on subsequent runs"
        )

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

    # Get changes metadata
    changes_metadata = state_manager.get_changes_metadata()
    total_changes = changes_metadata.get('total_count', len(recent_changes))
    
    # Format email content
    subject = (
        f"Kometa-AI Processing Report: {total_changes} changes, "
        f"{len(recent_errors)} errors"
    )

    message = NotificationFormatter.format_summary(
        changes=recent_changes,
        errors=recent_errors,
        next_run_time=next_run_time,
        collection_stats=results.get("collection_stats", {}),
        version=__version__,
        changes_metadata=changes_metadata
    )

    # Send notification
    recipients_str = ", ".join(email_notifier.recipients)
    logger.info(f"Sending notification email to {recipients_str}...")

    sent = email_notifier.send_notification(subject=subject, message=message)

    if sent:
        logger.info("Notification email sent successfully")
        # Clear errors and changes after successful notification to prevent stale data in future notifications
        state_manager.clear_errors()
        state_manager.clear_changes()
        # Save state after clearing
        state_manager.save()
        logger.info("Cleared error and change records from state after sending notification")
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

        if not all([radarr_url, radarr_api_key]):
            logger.error("Missing required API configuration")
            return 1

        # RadarrClient retries connection errors with backoff internally
        logger.info(f"Initializing Radarr client (URL: {radarr_url})...")
        radarr_client = RadarrClient(radarr_url, radarr_api_key, max_retries=10)
        if not radarr_client.test_connection():
            logger.error(f"Failed to connect to Radarr at {radarr_url}")
            return 1
        logger.info(f"Successfully connected to Radarr at {radarr_url}")

        logger.info("Initializing Claude client...")
        claude_client = make_claude_client()
        if claude_client is None:
            return 1

        kometa_parser = KometaParser(kometa_config_dir)

        def load_collections():
            logger.info("Loading collection configurations...")
            all_collections = kometa_parser.parse_configs()
            if args.collection:
                matched = [
                    c for c in all_collections
                    if c.name.lower() == args.collection.lower()
                ]
                if not matched:
                    logger.error(
                        f"Collection '{args.collection}' not found or not enabled")
                return matched
            return all_collections

        # Validate configuration before entering the schedule loop
        if not load_collections():
            return 1

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

            # Serialize the fetch→process→reconcile window across processes so a
            # scheduled run and a manual --run-now exec can't overlap and clobber
            # each other's Radarr tags. If another run holds the lock, skip this
            # cycle and retry on the next schedule.
            with acquire_run_lock(state_dir) as got_lock:
                if not got_lock:
                    results = None
                else:
                    # Refresh config and library each run — the daemon can run
                    # for weeks, and stale snapshots would miss new movies and
                    # re-apply tags against day-one state
                    collections = load_collections()
                    logger.info(f"Found {len(collections)} collections to process")
                    logger.info("Fetching movies from Radarr")
                    all_movies = radarr_client.get_movies()
                    logger.info(f"Retrieved {len(all_movies)} movies from Radarr")

                    # CLI --max-evals overrides the MAX_EVALS_PER_RUN env knob
                    max_evals = (
                        args.max_evals
                        if args.max_evals is not None
                        else Config.get_int("MAX_EVALS_PER_RUN", 0)
                    )
                    results = process_collections(
                        radarr_client=radarr_client,
                        claude_client=claude_client,
                        state_manager=state_manager,
                        collections=collections,
                        all_movies=all_movies,  # Pass the already fetched movies
                        dry_run=args.dry_run,
                        batch_size=args.batch_size,
                        force_refresh=args.force_refresh,
                        max_evals_per_run=max_evals
                    )

            if results is None:
                # Another run held the lock; nothing processed this cycle. Wait
                # for the next scheduled run and try again.
                next_run_time = calculate_schedule()
                formatted_next = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(
                    f"Run skipped (another run in progress), waiting until "
                    f"{formatted_next}")
                sleep_until(next_run_time)
                if terminate_requested:
                    logger.info(
                        "Termination requested during schedule wait, exiting")
                    break
                continue

            # Log the total cost spent on Claude API
            usage_stats = claude_client.get_usage_stats()
            total_cost = usage_stats.get('total_cost', 0.0)
            total_input_tokens = usage_stats.get('total_input_tokens', 0)
            total_output_tokens = usage_stats.get('total_output_tokens', 0)
            total_requests = usage_stats.get('requests', 0)
            
            logger.info(f"Claude API usage summary: ${total_cost:.4f} spent on {total_requests} requests "
                       f"({total_input_tokens:,} input tokens, {total_output_tokens:,} output tokens)")

            # The notification and the sleep must use the same next-run time
            next_run_time = calculate_schedule()

            # Send notifications
            send_notifications(
                results=results,
                state_manager=state_manager,
                next_run_time=next_run_time
            )

            if terminate_requested:
                logger.info("Termination requested, exiting")
                break

            # Sleep until next run
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


def ensure_required_directories_exist() -> bool:
    """
    Create required directories.
    This ensures the application can run without manual directory creation.
    
    Returns:
        bool: True if directories were created successfully, False otherwise
    """
    required_dirs = [
        os.path.join(os.getcwd(), "logs"),
        os.path.join(os.getcwd(), "state"),
        os.path.join(os.getcwd(), "state", "backups"),
    ]
    
    for directory in required_dirs:
        try:
            os.makedirs(directory, exist_ok=True)
        except (PermissionError, OSError) as e:
            # At this point, we can't use logging yet, so print the error
            print(f"ERROR: Failed to create directory {directory}: {str(e)}")
            print("Kometa-AI requires write access to logs and state directories.")
            print("Please ensure these directories exist and are writable.")
            return False
            
        # Check if the directory is writable by creating a test file
        test_file = os.path.join(directory, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except (PermissionError, OSError) as e:
            print(f"ERROR: Directory {directory} is not writable: {str(e)}")
            print("Kometa-AI requires write access to logs and state directories.")
            return False
    
    return True

def main(args: Optional[List[str]] = None) -> int:
    # Parse arguments
    parsed_args = parse_args(args)

    # Setup signal handlers
    setup_signal_handlers()

    # Show version if requested
    if parsed_args.version:
        print(f"Kometa-AI version {__version__}")
        return 0
        
    # Ensure directories exist before setting up logging
    if not ensure_required_directories_exist():
        print("ERROR: Failed to create or access required directories. Exiting.")
        return 1
    
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
        Config.dump()
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
