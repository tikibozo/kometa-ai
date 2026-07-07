"""Tests for the decision-consistency machinery: bounded near-threshold
re-evaluation, hysteresis (status-quo bias), revision accounting,
deterministic batching, and previous-decision anchoring."""

import json
import pytest

from kometa_ai.claude.processor import MovieProcessor, MAX_REVISIONS
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.radarr.models import Movie
from kometa_ai.state.manager import StateManager


class ScriptedClaudeClient:
    """Returns scripted decisions per movie; records every batch it receives."""

    def __init__(self):
        self.script = {}  # movie_id -> (include, confidence)
        self.batches = []  # list of parsed movie dicts per call

    def classify_movies(self, system_prompt, collection_prompt, movies_data):
        movies = json.loads(movies_data)
        self.batches.append(movies)
        decisions = []
        for m in movies:
            include, confidence = self.script[m["movie_id"]]
            decisions.append({
                "movie_id": m["movie_id"],
                "title": m["title"],
                "include": include,
                "confidence": confidence,
            })
        response = {"collection_name": "Test", "decisions": decisions}
        usage = {"total_input_tokens": 100, "total_output_tokens": 50,
                 "total_cost": 0.001, "requests": 1}
        return response, usage


@pytest.fixture
def collection():
    return CollectionConfig(
        name="Test", slug="test", enabled=True,
        prompt="Test criteria", confidence_threshold=0.7,
    )


@pytest.fixture
def state_manager(tmp_path):
    sm = StateManager(str(tmp_path / "state"))
    sm.load()
    return sm


@pytest.fixture
def client():
    return ScriptedClaudeClient()


def make_movie(movie_id, title=None):
    return Movie(id=movie_id, title=title or f"Movie {movie_id}",
                 year=2000, genres=["Drama"], overview="A test movie.")


def run(client, state_manager, collection, movies, force_refresh=False):
    processor = MovieProcessor(
        claude_client=client, state_manager=state_manager,
        force_refresh=force_refresh,
    )
    return processor.process_collection(collection, movies)


class TestBoundedReevaluation:
    def test_near_threshold_reevaluated_at_most_max_revisions_times(
            self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)  # near threshold -> churn candidate

        run(client, state_manager, collection, movies)
        assert len(client.batches) == 1

        # Re-evaluated once (revision budget), same verdict
        run(client, state_manager, collection, movies)
        assert len(client.batches) == 2
        assert state_manager.get_decision(1, "Test").revisions == MAX_REVISIONS

        # Budget exhausted: no further Claude calls, decision served from cache
        included, excluded, stats = run(client, state_manager, collection, movies)
        assert len(client.batches) == 2
        assert included == [1]

    def test_confident_decision_not_reevaluated(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.95)

        run(client, state_manager, collection, movies)
        included, _, _ = run(client, state_manager, collection, movies)

        assert len(client.batches) == 1
        assert included == [1]

    def test_metadata_change_resets_revisions(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)

        run(client, state_manager, collection, movies)
        run(client, state_manager, collection, movies)  # consumes revision budget
        assert state_manager.get_decision(1, "Test").revisions == MAX_REVISIONS

        # Metadata change triggers reprocessing and resets the budget
        changed = [make_movie(1, title="Movie 1 (Director's Cut)")]
        run(client, state_manager, collection, changed)
        assert len(client.batches) == 3
        assert state_manager.get_decision(1, "Test").revisions == 0


class TestHysteresis:
    def test_marginal_flip_is_rejected(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)
        run(client, state_manager, collection, movies)  # member

        # Re-evaluation wobbles just below threshold: 0.65 > 0.7 - 0.1 margin
        client.script[1] = (True, 0.65)
        included, excluded, _ = run(client, state_manager, collection, movies)

        assert included == [1]  # prior decision stands
        decision = state_manager.get_decision(1, "Test")
        assert decision.include is True
        assert decision.confidence == 0.72

    def test_decisive_flip_is_accepted(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)
        run(client, state_manager, collection, movies)  # member

        # Confident exclusion: score 1 - 0.8 = 0.2 <= 0.6 clears the margin
        client.script[1] = (False, 0.8)
        included, excluded, _ = run(client, state_manager, collection, movies)

        assert included == []
        assert excluded == [1]

    def test_marginal_join_is_rejected(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.6)  # below threshold -> not a member
        run(client, state_manager, collection, movies)

        # Wobbles just above threshold: 0.75 < 0.7 + 0.1 margin
        client.script[1] = (True, 0.75)
        included, excluded, _ = run(client, state_manager, collection, movies)

        assert included == []

    def test_decisive_join_is_accepted(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.6)
        run(client, state_manager, collection, movies)

        client.script[1] = (True, 0.9)  # 0.9 >= 0.8 clears the margin
        included, excluded, _ = run(client, state_manager, collection, movies)

        assert included == [1]

    def test_force_refresh_bypasses_hysteresis(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)
        run(client, state_manager, collection, movies)

        client.script[1] = (True, 0.65)  # would be rejected without force
        included, _, _ = run(client, state_manager, collection, movies, force_refresh=True)

        assert included == []
        assert state_manager.get_decision(1, "Test").confidence == 0.65


class TestDeterminism:
    def test_batches_are_sorted_by_movie_id(self, client, state_manager, collection):
        movies = [make_movie(3), make_movie(1), make_movie(2)]
        for m in movies:
            client.script[m.id] = (True, 0.9)

        run(client, state_manager, collection, movies)

        batch_ids = [m["movie_id"] for m in client.batches[0]]
        assert batch_ids == [1, 2, 3]


class TestPriorDecisionAnchoring:
    def test_reevaluated_movies_carry_previous_decision(
            self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.72)
        run(client, state_manager, collection, movies)

        run(client, state_manager, collection, movies)
        payload = client.batches[1][0]
        assert payload["previous_decision"] == {"include": True, "confidence": 0.72}

    def test_fresh_movies_have_no_previous_decision(
            self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (True, 0.9)
        run(client, state_manager, collection, movies)

        assert "previous_decision" not in client.batches[0][0]


class TestApplyStatusQuo:
    """Direct tests of the pure decision policy, including boundaries."""

    def _prior(self, include, confidence, revisions=0):
        from kometa_ai.state.models import DecisionRecord
        return DecisionRecord(
            movie_id=1, collection_name="Test", include=include,
            confidence=confidence, metadata_hash="h", tag="KAI-test",
            timestamp="2026-01-01T00:00:00Z", revisions=revisions,
        )

    def test_no_prior_passes_through(self):
        from kometa_ai.claude.processor import apply_status_quo
        include, confidence, reasoning, revisions = apply_status_quo(
            None, True, 0.9, "clear fit", 0.7, "no previous decision")
        assert (include, confidence, reasoning, revisions) == (True, 0.9, "clear fit", 0)

    def test_extreme_threshold_remains_flippable(self):
        from kometa_ai.claude.processor import apply_status_quo
        # threshold 0.95: flip-in gate would be 1.05 without clamping
        prior = self._prior(include=False, confidence=0.9)
        include, confidence, _, _ = apply_status_quo(
            prior, True, 1.0, None, 0.95, "metadata changed")
        assert include is True and confidence == 1.0

    def test_blocked_flip_keeps_prior_values(self):
        from kometa_ai.claude.processor import apply_status_quo
        prior = self._prior(include=True, confidence=0.9)
        include, confidence, reasoning, _ = apply_status_quo(
            prior, False, 0.35, "changed my mind a bit", 0.7, "metadata changed")
        # score 0.65 > 0.6 margin: status quo wins
        assert include is True and confidence == 0.9

    def test_exclusion_confidence_uses_membership_score(self):
        from kometa_ai.claude.processor import apply_status_quo
        prior = self._prior(include=True, confidence=0.9)
        # Confident exclusion: include=False at 0.8 -> score 0.2, flips out
        include, _, _, _ = apply_status_quo(
            prior, False, 0.8, None, 0.7, "metadata changed")
        assert include is False

    def test_revisions_increment_only_for_near_threshold(self):
        from kometa_ai.claude.processor import apply_status_quo, REASON_NEAR_THRESHOLD
        prior = self._prior(include=True, confidence=0.72, revisions=0)
        _, _, _, revisions = apply_status_quo(
            prior, True, 0.72, None, 0.7, REASON_NEAR_THRESHOLD)
        assert revisions == 1
        _, _, _, revisions = apply_status_quo(
            prior, True, 0.72, None, 0.7, "metadata changed")
        assert revisions == 0


class TestBorderlineExclusions:
    def test_borderline_exclusion_is_reevaluated(self, client, state_manager, collection):
        """include=False at low confidence is borderline (score near threshold)."""
        movies = [make_movie(1)]
        client.script[1] = (False, 0.35)  # score 0.65 -> within 0.15 of 0.7
        run(client, state_manager, collection, movies)

        run(client, state_manager, collection, movies)
        assert len(client.batches) == 2  # re-evaluated once

    def test_decisive_exclusion_is_not_reevaluated(self, client, state_manager, collection):
        movies = [make_movie(1)]
        client.script[1] = (False, 0.65)  # score 0.35 -> decisively out
        run(client, state_manager, collection, movies)

        run(client, state_manager, collection, movies)
        assert len(client.batches) == 1


class TestIncompleteResponses:
    def test_omitted_movies_keep_stored_membership(self, client, state_manager, collection):
        """Movies missing from Claude's response must not lose their tags."""
        movies = [make_movie(1), make_movie(2)]
        client.script[1] = (True, 0.95)
        client.script[2] = (True, 0.72)  # near threshold -> re-evaluated next run
        run(client, state_manager, collection, movies)

        # Second run: respond only for movie 2's companion... omit movie 2
        original = client.classify_movies

        def drop_movie_2(system_prompt, collection_prompt, movies_data):
            response, usage = original(system_prompt, collection_prompt, movies_data)
            response["decisions"] = [d for d in response["decisions"] if d["movie_id"] != 2]
            return response, usage

        client.classify_movies = drop_movie_2
        included, excluded, _ = run(client, state_manager, collection, movies)

        assert 2 in included  # stored membership preserved


class TestUsageLimit:
    def test_usage_limit_stops_batching_and_preserves_membership(
        self, client, state_manager, collection
    ):
        """A usage limit mid-run stops further batches, flags the processor,
        and keeps already-decided movies tagged (no spurious removals)."""
        from kometa_ai.claude.client import ClaudeUsageLimitError

        # Two batches worth; batch 2 hits the limit.
        movies = [make_movie(i) for i in range(1, 4)]
        for m in movies:
            client.script[m.id] = (True, 0.95)
        # First run decides everyone so we have stored membership.
        run(client, state_manager, collection, movies)

        # Force everyone back into processing, then fail on the second batch.
        processor = MovieProcessor(
            claude_client=client, state_manager=state_manager, batch_size=2,
            force_refresh=True,
        )
        original = client.classify_movies
        calls = {"n": 0}

        def limit_on_second(system_prompt, collection_prompt, movies_data):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise ClaudeUsageLimitError("usage limit reached")
            return original(system_prompt, collection_prompt, movies_data)

        client.classify_movies = limit_on_second
        included, excluded, _ = processor.process_collection(collection, movies)

        assert processor.usage_limited is True
        assert calls["n"] == 2  # stopped after the limit, did not try batch 3+
        # Every movie is still a member (batch 1 fresh, batch 2 from stored).
        assert set(included) == {1, 2, 3}
        assert excluded == []


class TestPromptHash:
    def _coll(self, prompt):
        return CollectionConfig(
            name="Test", slug="test", enabled=True,
            prompt=prompt, confidence_threshold=0.7,
        )

    def test_prompt_change_reevaluates_collection(self, client, state_manager):
        movies = [make_movie(1), make_movie(2)]
        client.script[1] = (True, 0.95)
        client.script[2] = (False, 0.9)

        run(client, state_manager, self._coll("criteria A"), movies)
        assert len(client.batches) == 1

        # Same prompt -> nothing reprocessed
        run(client, state_manager, self._coll("criteria A"), movies)
        assert len(client.batches) == 1

        # Changed prompt -> the collection is re-evaluated
        run(client, state_manager, self._coll("criteria B, stricter"), movies)
        assert len(client.batches) == 2

    def test_new_decisions_record_prompt_hash(self, client, state_manager):
        from kometa_ai.claude.processor import prompt_hash
        movies = [make_movie(1)]
        client.script[1] = (True, 0.95)
        run(client, state_manager, self._coll("criteria A"), movies)
        stored = state_manager.get_decision(1, "Test")
        assert stored.prompt_hash == prompt_hash("criteria A")

    def test_legacy_decision_backfilled_not_reevaluated(self, client, state_manager):
        from kometa_ai.claude.processor import prompt_hash
        from kometa_ai.state.models import DecisionRecord
        movie = make_movie(1)
        # A pre-prompt-hash record: metadata hash matches so only a prompt
        # change could reprocess it; prompt_hash is None (legacy).
        legacy = DecisionRecord(
            movie_id=1, collection_name="Test", include=True, confidence=0.95,
            metadata_hash=movie.calculate_metadata_hash(), tag="KAI-test",
            timestamp="2025-01-01T00:00:00+00:00", prompt_hash=None,
        )
        state_manager.set_decision(legacy)

        run(client, state_manager, self._coll("criteria A"), [movie])
        # Not re-evaluated (no Claude call)...
        assert client.batches == []
        # ...but the hash is backfilled so a future change is detectable.
        assert state_manager.get_decision(1, "Test").prompt_hash == prompt_hash("criteria A")

    def test_prompt_change_bypasses_hysteresis(self, client, state_manager):
        # A marginal flip that hysteresis would normally block is accepted when
        # the prompt itself changed (the prior verdict is against old criteria).
        movie = make_movie(1)
        client.script[1] = (True, 0.95)
        run(client, state_manager, self._coll("criteria A"), [movie])

        # New verdict: exclude at 0.35 -> membership score 0.65, inside the
        # hysteresis margin (would be kept as a member on a near-threshold
        # re-eval), but a prompt change forces a fresh judgment.
        client.script[1] = (False, 0.35)
        included, excluded, _ = run(client, state_manager, self._coll("criteria B"), [movie])
        assert included == []
        assert excluded == [1]
