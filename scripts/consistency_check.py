#!/usr/bin/env python3
"""Measure decision consistency across repeated Claude evaluations.

Runs each collection twice from a blank state (raw model consistency —
no anchoring or hysteresis can help, since there are no priors), reports
the flip rate between the two runs, then runs a third pass on top of the
second run's state (as a normal scheduled run would) and reports how many
memberships changed — which should be zero.

Usage:
  python scripts/consistency_check.py --movies test_data/synthetic_movies.json \
      --config-dir kometa-config [--collection "Heist Movies"] [--limit 50]

  # or against a live Radarr (read-only; no tags are written):
  RADARR_URL=... RADARR_API_KEY=... python scripts/consistency_check.py \
      --radarr --config-dir kometa-config --collection "Film Noir" --limit 100

Backend and model come from CLAUDE_BACKEND / CLAUDE_MODEL / CLAUDE_API_KEY.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kometa_ai.__main__ import make_claude_client  # noqa: E402
from kometa_ai.claude.processor import MovieProcessor  # noqa: E402
from kometa_ai.kometa.parser import KometaParser  # noqa: E402
from kometa_ai.radarr.models import Movie  # noqa: E402
from kometa_ai.state.manager import StateManager  # noqa: E402


def load_movies(args) -> list:
    if args.movies:
        with open(args.movies) as f:
            return [Movie.from_dict(m) for m in json.load(f)]
    if args.radarr:
        from kometa_ai.radarr.client import RadarrClient
        client = RadarrClient(os.environ["RADARR_URL"], os.environ["RADARR_API_KEY"])
        return client.get_movies()
    raise SystemExit("Provide --movies FILE or --radarr")


def evaluate(claude_client, collection, movies, state_dir) -> tuple:
    """One full evaluation into the given state dir; returns (included set, state manager)."""
    state = StateManager(state_dir)
    state.load()
    processor = MovieProcessor(claude_client=claude_client, state_manager=state)
    included, excluded, stats = processor.process_collection(collection, movies)
    return set(included), state, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--movies", help="JSON file of Radarr movie objects")
    parser.add_argument("--radarr", action="store_true", help="Fetch movies from Radarr (read-only)")
    parser.add_argument("--config-dir", required=True, help="Kometa config directory")
    parser.add_argument("--collection", help="Only check this collection")
    parser.add_argument("--limit", type=int, help="Evaluate at most N movies")
    args = parser.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    movies = load_movies(args)
    if args.limit:
        movies = sorted(movies, key=lambda m: m.id)[:args.limit]
    print(f"Evaluating {len(movies)} movies")

    collections = [c for c in KometaParser(args.config_dir).parse_configs() if c.enabled]
    if args.collection:
        collections = [c for c in collections if c.name.lower() == args.collection.lower()]
    if not collections:
        raise SystemExit("No enabled collections matched")

    claude_client = make_claude_client()
    if claude_client is None:
        raise SystemExit("Claude backend misconfigured")

    total_flips = 0
    total_movies = 0
    exit_code = 0
    for collection in collections:
        print(f"\n=== {collection.name} (threshold {collection.confidence_threshold}) ===")

        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            run1, _, _ = evaluate(claude_client, collection, movies, d1)
            run2, state2, _ = evaluate(claude_client, collection, movies, d2)

            flips = run1 ^ run2
            flip_rate = len(flips) / len(movies) if movies else 0
            total_flips += len(flips)
            total_movies += len(movies)

            print(f"Run 1: {len(run1)} included; Run 2: {len(run2)} included")
            print(f"Raw flip rate (blank state, no anchoring): "
                  f"{len(flips)}/{len(movies)} = {flip_rate:.1%}")
            by_id = {m.id: m.title for m in movies}
            for movie_id in sorted(flips):
                d = state2.get_decision(movie_id, collection.name)
                print(f"  FLIP: {by_id.get(movie_id, movie_id)} "
                      f"(run2: include={d.include}, confidence={d.confidence})" if d
                      else f"  FLIP: {by_id.get(movie_id, movie_id)}")

            # Stability pass: re-run on run 2's state like a normal scheduled run.
            # Bounded re-eval + anchoring + hysteresis should hold membership fixed.
            run3, _, stats3 = evaluate(claude_client, collection, movies, d2)
            changed = run2 ^ run3
            print(f"Stability pass: {stats3.get('processed_movies', 0)} "
                  f"movies re-evaluated, {len(changed)} membership changes")
            for movie_id in sorted(changed):
                print(f"  CHANGED: {by_id.get(movie_id, movie_id)}")

            if changed:
                exit_code = 1

    if total_movies:
        overall = total_flips / total_movies
        print(f"\nOverall raw flip rate: {total_flips}/{total_movies} = {overall:.1%}")
        if overall > 0.02:
            print("WARNING: raw flip rate above 2% target")
            exit_code = max(exit_code, 1)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
