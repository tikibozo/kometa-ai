"""Regression tests for one-shot vs daemon run semantics in the main pipeline.

Guards the fix for the incident where a `--dry-run --collection` validation run
entered the infinite scheduler loop (and acquired the run lock), becoming a rogue
daemon that woke on every schedule tick and blocked the real scheduled run.

The contract:
  * --dry-run: must NOT acquire the run lock (it writes no tags) and must run
    once then exit (not loop).
  * --collection (targeted, non-dry): still takes the lock, but runs once and
    exits.
  * daemon (--run-now, no dry-run/collection): takes the lock and loops
    (reaches the post-run sleep).
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch, MagicMock

import kometa_ai.__main__ as m


def _ns(**kw):
    base = dict(dry_run=False, collection=None, run_now=True,
                batch_size=None, force_refresh=False, max_evals=None)
    base.update(kw)
    return argparse.Namespace(**base)


@contextmanager
def _real_lock_cm(_state_dir):
    yield True


@contextmanager
def _harness():
    """Patch the pipeline's heavy deps so it reaches the run loop cheaply."""
    coll = MagicMock()
    coll.name = "Dark Comedies"
    claude = MagicMock()
    claude.get_usage_stats.return_value = {
        'total_cost': 0.0, 'total_input_tokens': 0,
        'total_output_tokens': 0, 'requests': 0,
    }

    with patch.object(m, 'StateManager'), \
         patch.object(m, 'RadarrClient') as rc, \
         patch.object(m, 'make_claude_client', return_value=claude), \
         patch.object(m, 'KometaParser') as kp, \
         patch.object(m, 'process_collections', return_value={}) as pc, \
         patch.object(m, 'send_notifications') as sn, \
         patch.object(m, 'calculate_schedule', return_value=datetime(2030, 1, 1)), \
         patch.object(m, 'sleep_until') as sleep, \
         patch.object(m, 'acquire_run_lock', side_effect=_real_lock_cm) as acq, \
         patch.object(m.Config, 'get', return_value='x'), \
         patch.object(m.Config, 'get_int', return_value=0):
        rc.return_value.test_connection.return_value = True
        rc.return_value.get_movies.return_value = []
        kp.return_value.parse_configs.return_value = [coll]
        yield {'acquire_run_lock': acq, 'sleep_until': sleep,
               'process_collections': pc, 'send_notifications': sn}


def test_dry_run_does_not_acquire_lock_and_exits():
    with _harness() as mk:
        rc = m.run_scheduled_pipeline(_ns(dry_run=True, run_now=True))
    assert rc == 0
    mk['acquire_run_lock'].assert_not_called()  # dry-run must not hold the lock
    mk['sleep_until'].assert_not_called()        # one-shot: no post-run sleep/loop
    mk['process_collections'].assert_called_once()


def test_collection_run_is_one_shot_and_takes_lock():
    with _harness() as mk:
        rc = m.run_scheduled_pipeline(
            _ns(dry_run=False, collection="Dark Comedies", run_now=True))
    assert rc == 0
    mk['acquire_run_lock'].assert_called_once()  # real targeted run still locks
    mk['sleep_until'].assert_not_called()         # one-shot: exits, no loop


def test_daemon_mode_takes_lock_and_loops():
    with _harness() as mk:
        # Break the otherwise-infinite loop right after the first post-run sleep.
        mk['sleep_until'].side_effect = KeyboardInterrupt
        try:
            m.run_scheduled_pipeline(_ns(dry_run=False, collection=None, run_now=True))
        except KeyboardInterrupt:
            pass
    mk['acquire_run_lock'].assert_called_once()
    mk['sleep_until'].assert_called_once()  # daemon reached the post-run sleep (would loop)
