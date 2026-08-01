"""Tests for the run/collection status section of the report email.

Covers the completeness view (members / pending / current-vs-backfilling) and
the run-level budget/quota lines added so the report shows what was deferred,
not just what changed.
"""
from kometa_ai.notification.formatter import NotificationFormatter as NF

COLLECTION_STATUS = {
    "Pride": {"members": 245, "candidates": 4855, "evaluated": 4855, "pending": 0},
    "Sapphic Cinema": {"members": 58, "candidates": 2400, "evaluated": 600, "pending": 1800},
    "Dark Comedies": {"members": 0, "candidates": 1200, "evaluated": 0, "pending": 1200},
}
RUN_STATUS = {"deferred": 8200, "usage_limited": True,
              "evals_used": 4000, "max_evals_per_run": 4000}


def test_status_rows_sorted_by_backlog_then_name():
    rows = NF._status_rows(COLLECTION_STATUS)
    names = [r[0] for r in rows]
    assert names == ["Sapphic Cinema", "Dark Comedies", "Pride"]  # most pending first
    # is_current flag (last element) only true when pending == 0
    current = {r[0]: r[4] for r in rows}
    assert current == {"Pride": True, "Sapphic Cinema": False, "Dark Comedies": False}


def test_run_status_lines():
    lines = NF._run_status_lines(RUN_STATUS)
    joined = " ".join(lines)
    assert "4000 of 4000" in joined            # budget usage
    assert "8200" in joined and "deferred" in joined
    assert "quota limit reached" in joined
    # nothing to say when the run was unconstrained
    assert NF._run_status_lines({"deferred": 0, "usage_limited": False,
                                 "evals_used": 10, "max_evals_per_run": 0}) == \
        ["Evaluations this run: 10"]


def test_plain_summary_includes_status_and_backlog():
    out = NF.format_summary(
        changes=[], errors=[], collection_status=COLLECTION_STATUS,
        run_status=RUN_STATUS)
    assert "-- Collection Status --" in out
    assert "Pride" in out and "current" in out
    assert "Sapphic Cinema" in out and "1800" in out and "backfilling" in out
    assert "Eval budget: 4000 of 4000 used this run" in out
    assert "8200 candidate(s) deferred" in out
    assert "quota limit reached" in out


def test_html_summary_includes_status_table():
    out = NF.format_summary_html(
        changes=[], errors=[], collection_status=COLLECTION_STATUS,
        run_status=RUN_STATUS)
    assert "Collection Status" in out
    assert "<table" in out and "Pending" in out
    assert ">current<" in out and ">backfilling<" in out
    assert "quota limit reached" in out


def test_no_status_section_when_absent():
    # Backward compatible: without collection_status, no status section appears.
    out = NF.format_summary(changes=[], errors=[])
    assert "Collection Status" not in out
    html = NF.format_summary_html(changes=[], errors=[])
    assert "Collection Status" not in html
