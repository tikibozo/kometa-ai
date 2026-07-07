import hashlib
import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, UTC

from kometa_ai.claude.client import ClaudeBackend, ClaudeUsageLimitError, DEFAULT_BATCH_SIZE
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

# Movies whose membership score is within this buffer of the threshold get
# re-evaluated (bounded by MAX_REVISIONS)
THRESHOLD_BUFFER = 0.15

# Reprocessing reasons — shared between selection and revision accounting
REASON_NO_DECISION = "no previous decision"
REASON_METADATA_CHANGED = "metadata changed"
REASON_NEAR_THRESHOLD = "near threshold confidence"
REASON_PROMPT_CHANGED = "collection prompt changed"


def prompt_hash(prompt: str) -> str:
    """Stable short hash of a collection prompt. A change means every stored
    decision for that collection was judged against different criteria and
    must be re-evaluated."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def membership_score(include: bool, confidence: float) -> float:
    """Estimated probability the movie belongs, regardless of which way the
    include flag points (confidence is confidence in the stated verdict)."""
    return confidence if include else 1.0 - confidence


def is_member(include: bool, confidence: float, threshold: float) -> bool:
    """The single membership rule: include verdict at or above the threshold."""
    return include and confidence >= threshold


def apply_status_quo(
    prior: Optional[DecisionRecord],
    include: bool,
    confidence: float,
    reasoning: Optional[str],
    threshold: float,
    reason: Optional[str],
    force_refresh: bool = False,
) -> Tuple[bool, float, Optional[str], int]:
    """Apply hysteresis and revision accounting to a fresh evaluation.

    A re-evaluation may only flip the stored decision if the new membership
    score clears the threshold by HYSTERESIS_MARGIN on the opposite side
    (clamped to [0, 1] so extreme thresholds remain flippable). Near-threshold
    re-evaluations consume the revision budget; everything else resets it.

    Returns:
        (include, confidence, reasoning, revisions) to record
    """
    # A prompt change invalidates the prior verdict (it was judged against
    # different criteria), so re-evaluate freshly — no status-quo anchoring.
    if prior is not None and not force_refresh and reason != REASON_PROMPT_CHANGED:
        new_score = membership_score(include, confidence)
        prior_member = is_member(prior.include, prior.confidence, threshold)
        new_member = is_member(include, confidence, threshold)
        if prior_member != new_member:
            flip_allowed = (
                new_score <= max(threshold - HYSTERESIS_MARGIN, 0.0)
                if prior_member
                else new_score >= min(threshold + HYSTERESIS_MARGIN, 1.0)
            )
            if not flip_allowed:
                include = prior.include
                confidence = prior.confidence
                reasoning = prior.reasoning

    if prior is not None and reason == REASON_NEAR_THRESHOLD:
        revisions = prior.revisions + 1
    else:
        revisions = 0

    return include, confidence, reasoning, revisions


class MovieProcessor:
    """Processes movies for classification using Claude."""

    def __init__(
        self,
        claude_client: ClaudeBackend,
        state_manager: StateManager,
        batch_size: Optional[int] = None,
        force_refresh: bool = False,
        max_evals_per_run: Optional[int] = None
    ):
        """Initialize the movie processor.

        Args:
            claude_client: Claude backend (API or CLI)
            state_manager: State manager for persisting decisions
            batch_size: Number of movies to process in each batch
            force_refresh: Force reprocessing of all movies, ignoring cached decisions
            max_evals_per_run: Soft cap on the number of movies sent to Claude
                across all collections in one run (Lever 2). None/0 means no
                cap. Near-threshold re-evaluations are never capped (they are
                the anti-oscillation guarantee); the backfill of new/changed
                collections is what gets paced. --force-refresh bypasses it.
        """
        self.claude_client = claude_client
        self.state_manager = state_manager
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.force_refresh = force_refresh
        self.max_evals_per_run = max_evals_per_run or 0
        self.system_prompt = get_system_prompt()

        # Metadata hashes are collection-independent; cache per movie so a
        # multi-collection run hashes each movie once
        self._hash_cache: Dict[int, str] = {}

        # Run-level count of movies sent to Claude, shared across every
        # collection processed by this processor instance (the budget pool).
        self.evals_used = 0

        # Store usage statistics for each collection
        self.collection_stats: Dict[str, Dict[str, Any]] = {}

        # Set when Claude declines further work because a usage/rate limit was
        # hit. It's a whole-run condition, so the caller should stop after the
        # current collection rather than start the next one.
        self.usage_limited = False

    def _budget_remaining(self) -> Optional[int]:
        """Movies still allowed to be sent to Claude this run, or None if the
        run is uncapped (no budget, or a force refresh)."""
        if self.force_refresh or not self.max_evals_per_run:
            return None
        return max(self.max_evals_per_run - self.evals_used, 0)

    def _priority_tier(
        self,
        movie: Movie,
        reason: Optional[str],
        existing_decisions: Dict[int, DecisionRecord],
        threshold: float,
    ) -> int:
        """Backfill priority (lower = processed first) within the budget-capped
        pool. Re-checking standing members of a changed collection comes before
        judging fresh non-members, so a prompt edit corrects Plex within one run
        even when the long tail is deferred."""
        decision = existing_decisions.get(movie.id)
        member = decision is not None and is_member(
            decision.include, decision.confidence, threshold
        )
        if reason == REASON_PROMPT_CHANGED:
            return 0 if member else 1
        if reason == REASON_METADATA_CHANGED:
            return 2
        if reason == REASON_NO_DECISION:
            return 4
        # Force-refresh (no reason recorded): members first so a tightening pass
        # re-checks standing members before the rest of the library.
        return 3 if member else 4

    def _record_filter_exclude(self, movie: Movie, collection: CollectionConfig) -> None:
        """Persist a deterministic exclude for a movie the candidate filter
        removed, demoting a standing member so reconcile drops its tag. Stores
        the current metadata hash so a later metadata change (e.g. the movie
        gains a qualifying genre) re-opens it for evaluation."""
        decision = DecisionRecord(
            movie_id=movie.id,
            collection_name=collection.name,
            include=False,
            confidence=1.0,
            metadata_hash=self._metadata_hash(movie),
            tag=collection.tag,
            timestamp=datetime.now(UTC).isoformat(),
            reasoning="Excluded by candidate filter (no Claude evaluation)",
            revisions=0,
            prompt_hash=prompt_hash(collection.prompt),
        )
        self.state_manager.set_decision(decision)

    def _metadata_hash(self, movie: Movie) -> str:
        h = self._hash_cache.get(movie.id)
        if h is None:
            h = movie.calculate_metadata_hash()
            self._hash_cache[movie.id] = h
        return h

    @staticmethod
    def _apply_cached(
        decision: DecisionRecord,
        threshold: float,
        included_ids: List[int],
        excluded_ids: List[int],
    ) -> None:
        """Route a stored decision into the included/excluded lists."""
        if is_member(decision.include, decision.confidence, threshold):
            included_ids.append(decision.movie_id)
        else:
            excluded_ids.append(decision.movie_id)

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

        threshold = collection.confidence_threshold
        logger.info(f"Processing collection '{collection.name}' with {len(movies)} movies")

        current_prompt_hash = prompt_hash(collection.prompt)

        included_ids: List[int] = []
        excluded_ids: List[int] = []

        # Lever 1 — candidate prefilter. Partition the library before any Claude
        # call: movies that can't plausibly belong are excluded for free. A
        # standing member that now fails the filter is demoted in state so
        # reconcile drops its tag.
        candidates: List[Movie] = []
        filtered_ids: List[int] = []
        filtered_demotions = 0
        for movie in movies:
            if collection.is_candidate(movie):
                candidates.append(movie)
                continue
            filtered_ids.append(movie.id)
            prior = self.state_manager.get_decision(movie.id, collection.name)
            if prior is not None and is_member(prior.include, prior.confidence, threshold):
                self._record_filter_exclude(movie, collection)
                filtered_demotions += 1
        excluded_ids.extend(filtered_ids)
        if filtered_ids:
            logger.info(
                f"Candidate filter kept {len(candidates)} of {len(movies)} movies for "
                f"'{collection.name}'; excluded {len(filtered_ids)} without a Claude call"
                + (f" ({filtered_demotions} demoted from the collection)" if filtered_demotions else "")
            )

        existing_decisions: Dict[int, DecisionRecord] = {}
        for movie in candidates:
            decision = self.state_manager.get_decision(movie.id, collection.name)
            if decision:
                existing_decisions[movie.id] = decision

        # Backfill prompt_hash on legacy records (pre-prompt-hash) without
        # re-evaluating — assume they're valid for the current prompt. This
        # anchors them so a LATER prompt change is detectable instead of being
        # permanently invisible. (Persisted by the caller's state save.)
        backfilled = 0
        for decision in existing_decisions.values():
            if decision.prompt_hash is None:
                decision.prompt_hash = current_prompt_hash
                self.state_manager.set_decision(decision)
                backfilled += 1
        if backfilled:
            logger.info(f"Backfilled prompt hash on {backfilled} legacy decisions for '{collection.name}'")

        # Determine which candidate movies need processing
        pending: List[Movie] = []
        reprocess_reasons: Dict[int, str] = {}
        if self.force_refresh:
            pending = list(candidates)
            logger.info(f"Force refresh requested, processing all {len(candidates)} candidate movies")
        else:
            # Process movies that:
            # 1. Don't have a previous decision
            # 2. Were judged against a now-changed prompt
            # 3. Have metadata changes
            # 4. Scored near the threshold, and haven't exhausted their
            #    re-evaluation budget (MAX_REVISIONS)
            for movie in candidates:
                current_hash = self._metadata_hash(movie)
                stored_hash = self.state_manager.get_metadata_hash(movie.id)
                decision = existing_decisions.get(movie.id)

                reason = None

                if not decision:
                    reason = REASON_NO_DECISION
                elif decision.prompt_hash is not None and decision.prompt_hash != current_prompt_hash:
                    reason = REASON_PROMPT_CHANGED
                elif stored_hash != current_hash:
                    reason = REASON_METADATA_CHANGED
                elif (decision.revisions < MAX_REVISIONS
                        and abs(membership_score(decision.include, decision.confidence)
                                - threshold) < THRESHOLD_BUFFER):
                    reason = REASON_NEAR_THRESHOLD

                if reason:
                    pending.append(movie)
                    reprocess_reasons[movie.id] = reason
                    logger.debug(f"Processing movie {movie.id} ({movie.title}): {reason}")

            logger.info(f"{len(pending)} of {len(candidates)} candidate movies need evaluation for collection '{collection.name}'")

        # Lever 2 — prioritized, budget-capped backfill. Near-threshold
        # re-evaluations always run (the bounded anti-oscillation pass); the
        # rest are ordered members-first and drawn against the shared run
        # budget. Deterministic sort keys keep batch composition stable.
        always = sorted(
            (m for m in pending if reprocess_reasons.get(m.id) == REASON_NEAR_THRESHOLD),
            key=lambda m: m.id,
        )
        capped = sorted(
            (m for m in pending if reprocess_reasons.get(m.id) != REASON_NEAR_THRESHOLD),
            key=lambda m: (
                self._priority_tier(m, reprocess_reasons.get(m.id), existing_decisions, threshold),
                m.id,
            ),
        )
        budget = self._budget_remaining()
        if budget is None:
            selected = always + capped
            deferred: List[Movie] = []
        else:
            take = max(budget - len(always), 0)
            selected = always + capped[:take]
            deferred = capped[take:]
        self.evals_used += len(selected)

        movies_to_process = selected
        to_process_ids = {movie.id for movie in movies_to_process}

        if deferred:
            logger.info(
                f"Budget cap: deferring {len(deferred)} of {len(pending)} pending movies for "
                f"'{collection.name}' to a future run "
                f"(MAX_EVALS_PER_RUN={self.max_evals_per_run}, {self._budget_remaining()} left this run)"
            )

        cached_count = sum(1 for movie_id in existing_decisions if movie_id not in to_process_ids)

        all_usage_stats: Dict[str, Any] = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'batches': 0,
            'processed_movies': 0,
            'from_cache': cached_count,
            'filtered': len(filtered_ids),
            'deferred': len(deferred),
        }

        # Movies with a stored decision that aren't being reprocessed this run
        # (stable, or deferred by the budget) keep their cached membership.
        for movie_id, decision in existing_decisions.items():
            if movie_id not in to_process_ids:
                self._apply_cached(decision, threshold, included_ids, excluded_ids)

        # Deferred movies with no prior decision stay untagged this run and are
        # retried next run (they remain REASON_NO_DECISION).
        for movie in deferred:
            if movie.id not in existing_decisions:
                excluded_ids.append(movie.id)

        # Nothing to send to Claude — everything was filtered, cached, or
        # deferred. Return the current membership.
        if not movies_to_process:
            logger.info(f"No movies need processing for collection '{collection.name}'")
            self.collection_stats[collection.name] = all_usage_stats
            included_ids = list(set(included_ids))
            excluded_ids = list(set(excluded_ids) - set(included_ids))
            return included_ids, excluded_ids, all_usage_stats

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
            # their previous decision (ignored on force refresh, and on a
            # prompt change — that prior verdict was made against different
            # criteria, so anchoring to it would bias toward the stale answer)
            batch_priors = None
            if not self.force_refresh:
                batch_priors = {
                    movie.id: existing_decisions[movie.id]
                    for movie in batch_movies
                    if movie.id in existing_decisions
                    and reprocess_reasons.get(movie.id) != REASON_PROMPT_CHANGED
                }
            movies_data = format_movies_data(batch_movies, batch_priors)

            # Call Claude
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

            except ClaudeUsageLimitError as e:
                # A usage limit is a whole-run condition: every remaining batch
                # would fail identically. Stop here rather than blast dozens of
                # instant failures; already-decided batches are checkpointed, so
                # the unprocessed movies simply resume on the next scheduled run.
                logger.warning(
                    f"Claude usage limit reached at batch {batch_index + 1}/{num_batches} "
                    f"for '{collection.name}'; stopping this run. "
                    f"Remaining movies resume on the next scheduled run. ({e})"
                )
                self.state_manager.log_error(
                    context=f"collection:{collection.name}",
                    error_message=f"Usage limit reached at batch {batch_index + 1}/{num_batches}; run stopped early"
                )
                self.usage_limited = True
                for movie in batch_movies:
                    prior = existing_decisions.get(movie.id)
                    if prior:
                        self._apply_cached(prior, threshold, included_ids, excluded_ids)
                break

            except Exception as e:
                logger.error(f"Error processing batch {batch_index + 1}: {e}")
                self.state_manager.log_error(
                    context=f"collection:{collection.name},batch:{batch_index + 1}",
                    error_message=str(e)
                )
                # Without a new decision, previously evaluated movies must
                # keep their stored membership — otherwise an API error would
                # strip tags from standing members
                for movie in batch_movies:
                    prior = existing_decisions.get(movie.id)
                    if prior:
                        self._apply_cached(prior, threshold, included_ids, excluded_ids)

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
        threshold = collection.confidence_threshold
        included_ids: List[int] = []
        excluded_ids: List[int] = []
        movie_map = {movie.id: movie for movie in batch_movies}
        decided_ids = set()

        for decision_data in decisions:
            movie_id = decision_data.get('movie_id')

            if movie_id not in movie_map:
                logger.warning(f"Decision for unknown movie ID: {movie_id}")
                continue

            movie = movie_map[movie_id]
            decided_ids.add(movie_id)
            prior = (prior_decisions or {}).get(movie_id)
            reason = (reprocess_reasons or {}).get(movie_id)
            raw_include = decision_data.get('include', False)

            include, confidence, reasoning, revisions = apply_status_quo(
                prior=prior,
                include=raw_include,
                confidence=decision_data.get('confidence', 0.0),
                reasoning=decision_data.get('reasoning'),
                threshold=threshold,
                reason=reason,
                force_refresh=self.force_refresh,
            )
            if prior is not None and include != raw_include:
                logger.info(
                    f"Keeping prior decision for movie {movie_id} ({movie.title}) "
                    f"in '{collection.name}': new evaluation did not clear the hysteresis margin"
                )

            # Create decision record
            decision = DecisionRecord(
                movie_id=movie_id,
                collection_name=collection.name,
                include=include,
                confidence=confidence,
                metadata_hash=self._metadata_hash(movie),
                tag=collection.tag,
                timestamp=datetime.now(UTC).isoformat(),
                reasoning=reasoning,
                revisions=revisions,
                prompt_hash=prompt_hash(collection.prompt)
            )

            # Store decision
            self.state_manager.set_decision(decision)

            # Add to included/excluded lists based on threshold
            if is_member(include, confidence, threshold):
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

        # Movies Claude omitted from the response keep their stored
        # membership — otherwise an incomplete response would strip tags
        missing = [m for m in batch_movies if m.id not in decided_ids]
        if missing:
            logger.warning(
                f"Claude response omitted {len(missing)} of {len(batch_movies)} movies "
                f"for '{collection.name}'; keeping their stored membership"
            )
            for movie in missing:
                prior = (prior_decisions or {}).get(movie.id)
                if prior:
                    self._apply_cached(prior, threshold, included_ids, excluded_ids)

        # Checkpoint state after each batch so a crash doesn't lose paid-for
        # decisions; skip the backup rotation (one backup per run is enough)
        self.state_manager.save(backup=False)

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
