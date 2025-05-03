import logging
import json
import math
import gc
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, UTC

from kometa_ai.claude.client import ClaudeClient, DEFAULT_BATCH_SIZE
from kometa_ai.claude.prompts import get_system_prompt, format_collection_prompt, format_movies_data
from kometa_ai.radarr.models import Movie
from kometa_ai.kometa.models import CollectionConfig
# Try to import state modules, but don't fail if they don't exist
try:
    from kometa_ai.state.manager import StateManager
    from kometa_ai.state.models import DecisionRecord
except ImportError:
    # Create simple mock classes for testing
    class StateManager:
        def __init__(self, *args, **kwargs):
            pass
        def load(self):
            pass
        def save(self):
            pass
        def log_change(self, *args, **kwargs):
            pass
        def log_error(self, *args, **kwargs):
            pass
    
    class DecisionRecord:
        def __init__(self, *args, **kwargs):
            pass
from kometa_ai.utils.profiling import profile_time, profile_memory
from kometa_ai.utils.memory_optimization import optimize_movie_objects, process_in_chunks, clear_memory
from kometa_ai.utils.error_handling import (
    handle_error, retry_with_backoff,
    ErrorCategory, ErrorContext, recover_from_memory_error
)

logger = logging.getLogger(__name__)

# Global variable for graceful termination
terminate_requested = False


class MovieProcessor:
    """Processes movies for classification using Claude."""

    def __init__(
        self,
        claude_client: ClaudeClient,
        state_manager: StateManager,
        batch_size: Optional[int] = None,
        force_refresh: bool = False
    ):
        """Initialize the movie processor.

        Args:
            claude_client: Claude API client
            state_manager: State manager for persisting decisions
            batch_size: Number of movies to process in each batch
            force_refresh: Force reprocessing of all movies, ignoring cached decisions
        """
        self.claude_client = claude_client
        self.state_manager = state_manager
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.force_refresh = force_refresh
        self.system_prompt = get_system_prompt()

        # Store usage statistics for each collection
        self.collection_stats: Dict[str, Dict[str, Any]] = {}

    @profile_time
    def process_collection(
        self,
        collection: CollectionConfig,
        movies: List[Movie]
    ) -> Tuple[List[int], List[int], Dict[str, Any]]:
        """Process a collection and determine which movies to include.

        Args:
            collection: Collection configuration
            movies: List of all movies

        Returns:
            Tuple of (included movie IDs, excluded movie IDs, usage stats)
        """
        if not collection.enabled:
            logger.info(f"Collection '{collection.name}' is disabled, skipping")
            return [], [], {}

        # Determine memory-efficient batch size for very large libraries
        original_count = len(movies)
        movies_per_worker = min(1000, original_count)  # Cap at 1000 movies per processing chunk

        logger.info(f"Processing collection '{collection.name}' with {original_count} movies")

        # For large libraries, optimize movie objects to reduce memory usage
        if original_count > 1000:
            logger.info(f"Optimizing memory usage for large library ({original_count} movies)")
            movies = optimize_movie_objects(movies)

        # Get existing decisions and metadata hashes - only load what we need
        existing_decisions = {}
        # Use smaller chunks to process very large libraries
        chunk_size = 500

        for i in range(0, len(movies), chunk_size):
            chunk = movies[i:i + chunk_size]
            for movie in chunk:
                decision = self.state_manager.get_decision(movie.id, collection.name)
                if decision:
                    existing_decisions[movie.id] = decision

        # Determine which movies need processing
        movies_to_process = []
        if self.force_refresh:
            movies_to_process = movies
            logger.info(f"Force refresh requested, processing all {len(movies)} movies")
        else:
            # Process movies that:
            # 1. Don't have a previous decision
            # 2. Have metadata changes
            # 3. Had a confidence score near the threshold
            threshold_buffer = 0.15  # Reprocess movies near threshold
            for movie in movies:
                current_hash = movie.calculate_metadata_hash()
                stored_hash = self.state_manager.get_metadata_hash(movie.id)
                decision = existing_decisions.get(movie.id)

                should_process = False
                reason = None

                if not decision:
                    should_process = True
                    reason = "no previous decision"
                elif stored_hash != current_hash:
                    should_process = True
                    reason = "metadata changed"
                elif abs(decision.confidence - collection.confidence_threshold) < threshold_buffer:
                    should_process = True
                    reason = "near threshold confidence"

                if should_process:
                    movies_to_process.append(movie)
                    if reason:
                        logger.debug(f"Processing movie {movie.id} ({movie.title}): {reason}")

            logger.info(f"Processing {len(movies_to_process)} of {len(movies)} movies for collection '{collection.name}'")

        # If no movies need processing, use existing decisions
        if not movies_to_process:
            logger.info(f"No movies need processing for collection '{collection.name}'")
            included_ids = []
            excluded_ids = []

            for movie_id, decision in existing_decisions.items():
                if decision.include and decision.confidence >= collection.confidence_threshold:
                    included_ids.append(movie_id)
                else:
                    excluded_ids.append(movie_id)

            return included_ids, excluded_ids, {"movie_count": len(movies), "processed": 0, "from_cache": len(existing_decisions)}

        # Process in batches
        included_ids = []
        excluded_ids = []
        all_usage_stats = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'batches': 0,
            'processed_movies': 0,
            'from_cache': len(existing_decisions) - len(movies_to_process)
        }

        # Reserve existing decisions for movies not being reprocessed
        for movie in movies:
            if movie not in movies_to_process and movie.id in existing_decisions:
                decision = existing_decisions[movie.id]
                if decision.include and decision.confidence >= collection.confidence_threshold:
                    included_ids.append(movie.id)
                else:
                    excluded_ids.append(movie.id)

        # Allow decisions to be garbage collected once processed
        clear_memory()

        # Process movies in batches
        collection_prompt = format_collection_prompt(collection)
        logger.debug(f"Generated collection prompt for '{collection.name}'. Length: {len(collection_prompt)}")
        if len(collection_prompt.strip()) < 50:
            logger.warning(f"Collection prompt for '{collection.name}' is suspiciously short. Check configuration.")
        num_batches = math.ceil(len(movies_to_process) / self.batch_size)

        # For very large libraries, use parallel processing if available
        for batch_index in range(num_batches):
            # Check for termination - use a try/except to handle the case where the variable isn't defined
            try:
                if terminate_requested:
                    logger.warning("Termination requested, stopping batch processing")
                    break
            except NameError:
                # terminate_requested is not defined in the module scope, ignore
                pass

            start_idx = batch_index * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(movies_to_process))
            batch_movies = movies_to_process[start_idx:end_idx]

            logger.info(f"Processing batch {batch_index + 1}/{num_batches} with {len(batch_movies)} movies")

            # Format movie data for this batch
            movies_data = format_movies_data(batch_movies)

            # Call Claude API
            try:
                response, usage_stats = self.claude_client.classify_movies(
                    self.system_prompt,
                    collection_prompt,
                    movies_data,
                    self.batch_size
                )

                # Accumulate usage stats
                all_usage_stats['total_input_tokens'] += usage_stats.get('total_input_tokens', 0)
                all_usage_stats['total_output_tokens'] += usage_stats.get('total_output_tokens', 0)
                all_usage_stats['total_cost'] += usage_stats.get('total_cost', 0.0)
                all_usage_stats['requests'] += usage_stats.get('requests', 0)
                all_usage_stats['batches'] += 1
                all_usage_stats['processed_movies'] += len(batch_movies)

                # Process decisions
                batch_included, batch_excluded = self._process_decisions(
                    response, collection, batch_movies
                )

                included_ids.extend(batch_included)
                excluded_ids.extend(batch_excluded)

                # Force garbage collection after each batch to reduce memory usage
                # This is especially important for large libraries
                if original_count > 1000:
                    clear_memory()

            except Exception as e:
                logger.error(f"Error processing batch {batch_index + 1}: {e}")
                self.state_manager.log_error(
                    context=f"collection:{collection.name},batch:{batch_index + 1}",
                    error_message=str(e)
                )

                # If we hit an error due to memory issues, try to recover
                # by forcing garbage collection
                clear_memory()

        # Store collection-specific stats
        self.collection_stats[collection.name] = all_usage_stats

        # Remove duplicates (a movie might appear in both included and excluded due to batching)
        included_ids = list(set(included_ids))
        excluded_ids = list(set(excluded_ids) - set(included_ids))

        logger.info(
            f"Collection '{collection.name}' processing complete: "
            f"{len(included_ids)} included, {len(excluded_ids)} excluded"
        )

        return included_ids, excluded_ids, all_usage_stats

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def _process_decisions(
        self,
        response: Dict[str, Any],
        collection: CollectionConfig,
        batch_movies: List[Movie]
    ) -> Tuple[List[int], List[int]]:
        """Process decisions from Claude's response.

        Args:
            response: Claude API response
            collection: Collection configuration
            batch_movies: List of movies in this batch

        Returns:
            Tuple of (included movie IDs, excluded movie IDs)
        """
        try:
            if 'decisions' not in response:
                logger.error(f"Invalid response format: {response}")
                raise ValueError("Invalid response format: missing 'decisions' key")

            decisions = response['decisions']
            included_ids = []
            excluded_ids = []
            movie_map = {movie.id: movie for movie in batch_movies}

            for decision_data in decisions:
                movie_id = decision_data.get('movie_id')

                if movie_id not in movie_map:
                    logger.warning(f"Decision for unknown movie ID: {movie_id}")
                    continue

                movie = movie_map[movie_id]
                include = decision_data.get('include', False)
                confidence = decision_data.get('confidence', 0.0)
                reasoning = decision_data.get('reasoning')

                # Create decision record
                decision = DecisionRecord(
                    movie_id=movie_id,
                    collection_name=collection.name,
                    include=include,
                    confidence=confidence,
                    metadata_hash=movie.calculate_metadata_hash(),
                    tag=collection.tag,
                    timestamp=datetime.now(UTC).isoformat(),
                    reasoning=reasoning
                )

                # Store decision
                self.state_manager.set_decision(decision)

                # Add to included/excluded lists based on threshold
                if include and confidence >= collection.confidence_threshold:
                    included_ids.append(movie_id)
                    logger.debug(
                        f"Including movie {movie_id} ({movie.title}) in collection '{collection.name}' "
                        f"with confidence {confidence:.2f}"
                    )
                else:
                    excluded_ids.append(movie_id)
                    logger.debug(
                        f"Excluding movie {movie_id} ({movie.title}) from collection '{collection.name}' "
                        f"with confidence {confidence:.2f}"
                    )

            # Checkpoint state after each batch to ensure we don't lose decisions
            # if we crash later
            self.state_manager.save()

            return included_ids, excluded_ids

        except Exception as e:
            # Handle specific error types with recovery strategies
            context = f"process_decisions:{collection.name}"
            should_retry, error_ctx = handle_error(
                error=e,
                context=context,
                state_manager=self.state_manager
            )

            # Add additional context to error for better debugging
            error_ctx.additional_info = {
                'collection_name': collection.name,
                'batch_size': len(batch_movies),
                'response_keys': list(response.keys()) if isinstance(response, dict) else None
            }

            # Attempt error-specific recovery
            if isinstance(e, MemoryError) or 'memory' in str(e).lower():
                recover_from_memory_error(error_ctx)

            # Re-raise to let retry decorator handle it
            raise

    def get_collection_stats(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for collections.

        Args:
            collection_name: Optional collection name to get stats for

        Returns:
            Dictionary with usage statistics
        """
        if collection_name:
            return self.collection_stats.get(collection_name, {})
        return self.collection_stats
