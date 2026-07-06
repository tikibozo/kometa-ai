import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, UTC

from kometa_ai.claude.client import ClaudeClient, DEFAULT_BATCH_SIZE
from kometa_ai.claude.prompts import get_system_prompt, format_collection_prompt, format_movies_data
from kometa_ai.radarr.models import Movie
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

logger = logging.getLogger(__name__)

# Maximum number of near-threshold re-evaluations per movie/collection pair.
# Without this bound, movies whose confidence lands near the threshold are
# re-sent to Claude on every run and their membership oscillates.
MAX_REVISIONS = 1

# A re-evaluation may only flip a previous decision if the new confidence
# clears the threshold by this margin on the opposite side (status quo bias).
HYSTERESIS_MARGIN = 0.1


def is_member(include: bool, confidence: float, threshold: float) -> bool:
    """The single membership rule: include verdict at or above the threshold."""
    return include and confidence >= threshold


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

        logger.info(f"Processing collection '{collection.name}' with {len(movies)} movies")

        existing_decisions: Dict[int, DecisionRecord] = {}
        for movie in movies:
            decision = self.state_manager.get_decision(movie.id, collection.name)
            if decision:
                existing_decisions[movie.id] = decision

        # Determine which movies need processing
        movies_to_process = []
        reprocess_reasons: Dict[int, str] = {}
        if self.force_refresh:
            movies_to_process = list(movies)
            logger.info(f"Force refresh requested, processing all {len(movies)} movies")
        else:
            # Process movies that:
            # 1. Don't have a previous decision
            # 2. Have metadata changes
            # 3. Had a confidence score near the threshold, and haven't
            #    exhausted their re-evaluation budget (MAX_REVISIONS)
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
                elif (decision.revisions < MAX_REVISIONS
                        and abs(decision.confidence - collection.confidence_threshold) < threshold_buffer):
                    should_process = True
                    reason = "near threshold confidence"

                if should_process:
                    movies_to_process.append(movie)
                    if reason:
                        reprocess_reasons[movie.id] = reason
                        logger.debug(f"Processing movie {movie.id} ({movie.title}): {reason}")

            logger.info(f"Processing {len(movies_to_process)} of {len(movies)} movies for collection '{collection.name}'")

        # Sort so identical inputs always produce identical batches; batch
        # composition affects Claude's judgments, so keep it deterministic.
        movies_to_process.sort(key=lambda m: m.id)

        # If no movies need processing, use existing decisions
        if not movies_to_process:
            logger.info(f"No movies need processing for collection '{collection.name}'")
            included_ids = []
            excluded_ids = []

            for movie_id, decision in existing_decisions.items():
                if is_member(decision.include, decision.confidence, collection.confidence_threshold):
                    included_ids.append(movie_id)
                else:
                    excluded_ids.append(movie_id)

            return included_ids, excluded_ids, {"movie_count": len(movies), "processed_movies": 0, "from_cache": len(existing_decisions)}

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
        to_process_ids = {movie.id for movie in movies_to_process}
        for movie in movies:
            if movie.id not in to_process_ids and movie.id in existing_decisions:
                decision = existing_decisions[movie.id]
                if is_member(decision.include, decision.confidence, collection.confidence_threshold):
                    included_ids.append(movie.id)
                else:
                    excluded_ids.append(movie.id)

        # Process movies in batches
        collection_prompt = format_collection_prompt(collection)
        logger.debug(f"Generated collection prompt for '{collection.name}'. Length: {len(collection_prompt)}")
        if len(collection_prompt.strip()) < 50:
            logger.warning(f"Collection prompt for '{collection.name}' is suspiciously short. Check configuration.")
        num_batches = math.ceil(len(movies_to_process) / self.batch_size)

        for batch_index in range(num_batches):
            start_idx = batch_index * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(movies_to_process))
            batch_movies = movies_to_process[start_idx:end_idx]

            logger.info(f"Processing batch {batch_index + 1}/{num_batches} with {len(batch_movies)} movies")

            # Format movie data for this batch, anchoring re-evaluations to
            # their previous decision (ignored on force refresh)
            batch_priors = None
            if not self.force_refresh:
                batch_priors = {
                    movie.id: existing_decisions[movie.id]
                    for movie in batch_movies
                    if movie.id in existing_decisions
                }
            movies_data = format_movies_data(batch_movies, batch_priors)

            # Call Claude API
            try:
                response, usage_stats = self.claude_client.classify_movies(
                    self.system_prompt,
                    collection_prompt,
                    movies_data
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
                    response, collection, batch_movies, reprocess_reasons,
                    existing_decisions
                )

                included_ids.extend(batch_included)
                excluded_ids.extend(batch_excluded)

            except Exception as e:
                logger.error(f"Error processing batch {batch_index + 1}: {e}")
                self.state_manager.log_error(
                    context=f"collection:{collection.name},batch:{batch_index + 1}",
                    error_message=str(e)
                )
                # Preserve existing membership for this batch: without a new
                # decision, a previously tagged movie would otherwise be
                # treated as "not included" and lose its tag on an API error
                for movie in batch_movies:
                    prior = existing_decisions.get(movie.id)
                    if prior and is_member(prior.include, prior.confidence,
                                           collection.confidence_threshold):
                        included_ids.append(movie.id)

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

    def _process_decisions(
        self,
        response: Dict[str, Any],
        collection: CollectionConfig,
        batch_movies: List[Movie],
        reprocess_reasons: Optional[Dict[int, str]] = None,
        prior_decisions: Optional[Dict[int, DecisionRecord]] = None
    ) -> Tuple[List[int], List[int]]:
        """Process decisions from Claude's response.

        Args:
            response: Claude API response
            collection: Collection configuration
            batch_movies: List of movies in this batch
            reprocess_reasons: Why each movie was re-evaluated (keyed by movie
                ID); used for hysteresis and revision accounting
            prior_decisions: Stored decisions from before this run — the same
                dict used for prompt anchoring, so hysteresis judges against
                exactly what Claude was shown

        Returns:
            Tuple of (included movie IDs, excluded movie IDs)
        """
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

            # Apply status-quo bias: a re-evaluation may only flip the
            # stored decision if it clears the threshold by the hysteresis
            # margin on the opposite side. Otherwise keep the prior call.
            reason = (reprocess_reasons or {}).get(movie_id)
            prior = (prior_decisions or {}).get(movie_id)
            threshold = collection.confidence_threshold
            if prior is not None and not self.force_refresh:
                # Estimated probability the movie belongs, regardless of
                # which way the include flag points
                new_score = confidence if include else 1.0 - confidence
                prior_member = is_member(prior.include, prior.confidence, threshold)
                new_member = is_member(include, confidence, threshold)
                if prior_member != new_member:
                    flip_allowed = (
                        new_score <= threshold - HYSTERESIS_MARGIN
                        if prior_member
                        else new_score >= threshold + HYSTERESIS_MARGIN
                    )
                    if not flip_allowed:
                        logger.info(
                            f"Keeping prior decision for movie {movie_id} ({movie.title}) "
                            f"in '{collection.name}': new evaluation "
                            f"(include={include}, confidence={confidence:.2f}) does not "
                            f"clear the hysteresis margin"
                        )
                        include = prior.include
                        confidence = prior.confidence
                        reasoning = prior.reasoning

            # Near-threshold re-evaluations consume the revision budget;
            # fresh evaluations and metadata changes reset it
            if prior is not None and reason == "near threshold confidence":
                revisions = prior.revisions + 1
            else:
                revisions = 0

            # Create decision record
            decision = DecisionRecord(
                movie_id=movie_id,
                collection_name=collection.name,
                include=include,
                confidence=confidence,
                metadata_hash=movie.calculate_metadata_hash(),
                tag=collection.tag,
                timestamp=datetime.now(UTC).isoformat(),
                reasoning=reasoning,
                revisions=revisions
            )

            # Store decision
            self.state_manager.set_decision(decision)

            # Add to included/excluded lists based on threshold
            if is_member(include, confidence, collection.confidence_threshold):
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
