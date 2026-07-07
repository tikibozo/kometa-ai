"""Tests for Lever 1 (candidate prefilter in the processor) and Lever 2
(bounded, prioritized backfill): the filter partition, the per-run evaluation
budget, priority ordering, near-threshold carve-out, and cross-collection
budget sharing."""

import json
import pytest

from kometa_ai.claude.processor import MovieProcessor, prompt_hash
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
        decisions = [
            {"movie_id": m["movie_id"], "title": m["title"],
             "include": self.script[m["movie_id"]][0],
             "confidence": self.script[m["movie_id"]][1]}
            for m in movies
        ]
        usage = {"total_input_tokens": 100, "total_output_tokens": 50,
                 "total_cost": 0.001, "requests": 1}
        return {"collection_name": "Test", "decisions": decisions}, usage

    def all_seen_ids(self):
        return {m["movie_id"] for batch in self.batches for m in batch}


@pytest.fixture
def state_manager(tmp_path):
    sm = StateManager(str(tmp_path / "state"))
    sm.load()
    return sm


@pytest.fixture
def client():
    return ScriptedClaudeClient()


def mv(movie_id, genres=None, year=2000):
    return Movie(id=movie_id, title=f"Movie {movie_id}", year=year,
                 genres=genres or ["Drama"], overview="A test movie.")


def run(client, state_manager, collection, movies, max_evals_per_run=None,
        force_refresh=False):
    processor = MovieProcessor(
        claude_client=client, state_manager=state_manager,
        force_refresh=force_refresh, max_evals_per_run=max_evals_per_run,
    )
    return processor.process_collection(collection, movies)


class TestCandidatePrefilter:
    def test_non_candidates_excluded_without_claude(self, client, state_manager):
        collection = CollectionConfig(
            name="Heist", slug="heist", enabled=True, prompt="heist",
            candidate_genres=["Crime"],
        )
        movies = [mv(1, genres=["Crime"]), mv(2, genres=["Romance"])]
        client.script[1] = (True, 0.9)

        included, excluded, stats = run(client, state_manager, collection, movies)

        assert 2 not in client.all_seen_ids()   # never sent to Claude
        assert included == [1]
        assert 2 in excluded
        assert stats["filtered"] == 1

    def test_filter_demotes_standing_member(self, client, state_manager):
        # First run with no filter: movie 2 becomes a member.
        no_filter = CollectionConfig(name="C", slug="c", enabled=True, prompt="p")
        movies = [mv(2, genres=["Romance"])]
        client.script[2] = (True, 0.9)
        included, _, _ = run(client, state_manager, no_filter, movies)
        assert included == [2]

        # Now a filter excludes Romance: movie 2 must be demoted.
        filtered = CollectionConfig(name="C", slug="c", enabled=True, prompt="p",
                                    candidate_genres=["Crime"])
        included, excluded, _ = run(client, state_manager, filtered, movies)
        assert included == []
        assert 2 in excluded
        assert state_manager.get_decision(2, "C").include is False


class TestBudgetCap:
    def test_only_budget_worth_processed_then_resumes(self, client, state_manager):
        collection = CollectionConfig(name="C", slug="c", enabled=True, prompt="p")
        movies = [mv(i) for i in range(1, 5)]  # 4 new movies
        for i in range(1, 5):
            client.script[i] = (True, 0.9)

        # Budget of 2: only 2 movies sent to Claude this run (lowest ids first,
        # all being equal-tier NO_DECISION backfill).
        inc1, exc1, stats1 = run(client, state_manager, collection, movies,
                                 max_evals_per_run=2)
        assert client.all_seen_ids() == {1, 2}
        assert stats1["deferred"] == 2
        assert {i for i in range(1, 5) if state_manager.get_decision(i, "C")} == {1, 2}

        # Next run: the 2 decided drop out (cached), the 2 deferred resume.
        client.batches.clear()
        inc2, exc2, stats2 = run(client, state_manager, collection, movies,
                                 max_evals_per_run=2)
        assert client.all_seen_ids() == {3, 4}
        assert stats2["deferred"] == 0
        assert set(inc2) == {1, 2, 3, 4}   # all members now

    def test_deferred_new_movie_not_persisted(self, client, state_manager):
        collection = CollectionConfig(name="C", slug="c", enabled=True, prompt="p")
        movies = [mv(1), mv(2)]
        client.script[1] = (True, 0.9)
        client.script[2] = (True, 0.9)

        run(client, state_manager, collection, movies, max_evals_per_run=1)

        # Exactly one decided; the deferred one has no stored decision so it is
        # retried (still REASON_NO_DECISION) next run.
        decided = [i for i in (1, 2) if state_manager.get_decision(i, "C")]
        assert len(decided) == 1


class TestPriority:
    def test_members_reevaluated_before_new_backfill(self, client, state_manager):
        # Establish movie 1 as a member under prompt A (no budget).
        col_a = CollectionConfig(name="C", slug="c", enabled=True, prompt="AAA")
        client.script[1] = (True, 0.9)
        run(client, state_manager, col_a, [mv(1)])

        # Prompt changes to B and three new movies appear; budget of 1.
        col_b = CollectionConfig(name="C", slug="c", enabled=True, prompt="BBB")
        movies = [mv(1), mv(2), mv(3), mv(4)]
        for i in range(1, 5):
            client.script[i] = (True, 0.9)
        client.batches.clear()

        run(client, state_manager, col_b, movies, max_evals_per_run=1)

        # The single unit of budget went to the standing member, not a new movie.
        assert client.all_seen_ids() == {1}
        assert state_manager.get_decision(1, "C").prompt_hash == prompt_hash("BBB")
        for new_id in (2, 3, 4):
            assert state_manager.get_decision(new_id, "C") is None

    def test_near_threshold_bypasses_budget(self, client, state_manager):
        # Seed two near-threshold members (no budget).
        collection = CollectionConfig(name="C", slug="c", enabled=True,
                                      prompt="p", confidence_threshold=0.7)
        client.script[1] = (True, 0.72)
        client.script[2] = (True, 0.72)
        run(client, state_manager, collection, [mv(1), mv(2)])

        # Next run: budget of 1, plus a new movie. Both near-threshold
        # re-evaluations must still run (they are the anti-oscillation pass),
        # while the new movie is deferred.
        client.batches.clear()
        client.script[3] = (True, 0.9)
        run(client, state_manager, collection, [mv(1), mv(2), mv(3)],
            max_evals_per_run=1)

        assert client.all_seen_ids() == {1, 2}
        assert state_manager.get_decision(3, "C") is None


class TestCrossCollectionBudget:
    def test_budget_shared_across_collections(self, client, state_manager):
        col1 = CollectionConfig(name="C1", slug="c1", enabled=True, prompt="p1")
        col2 = CollectionConfig(name="C2", slug="c2", enabled=True, prompt="p2")
        movies = [mv(i) for i in range(1, 5)]
        for i in range(1, 5):
            client.script[i] = (True, 0.9)

        # One processor (one run) with a budget of 3 spanning both collections.
        processor = MovieProcessor(
            claude_client=client, state_manager=state_manager,
            max_evals_per_run=3,
        )
        processor.process_collection(col1, movies)
        processor.process_collection(col2, movies)

        # Total movies sent to Claude across both collections is capped at 3.
        total_sent = sum(len(b) for b in client.batches)
        assert total_sent == 3
        assert processor.evals_used == 3
