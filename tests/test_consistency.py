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
