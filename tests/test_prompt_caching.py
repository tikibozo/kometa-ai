"""Tests for Lever 5 (prompt caching): cache-aware cost accounting and that
cached input is reported in the usage totals."""

from unittest.mock import MagicMock

from kometa_ai.claude.client import ClaudeClient


def _usage(input_tokens, output_tokens, cache_read=0, cache_write=0):
    u = MagicMock()
    u.input_tokens = input_tokens
    u.output_tokens = output_tokens
    u.cache_read_input_tokens = cache_read
    u.cache_creation_input_tokens = cache_write
    resp = MagicMock()
    resp.usage = u
    return resp


def test_cache_read_is_cheaper_than_fresh_input():
    """1000 cached-read tokens cost less than 1000 fresh input tokens."""
    client = ClaudeClient(api_key="k", model="claude-sonnet-5")
    fresh = client._calculate_cost(input_tokens=2000, output_tokens=500)
    cached = client._calculate_cost(
        input_tokens=1000, output_tokens=500, cache_read_tokens=1000
    )
    assert cached < fresh
    # cache read billed at 0.1x: billable input = 1000 + 100 = 1100
    assert cached == (1100 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0


def test_cache_write_billed_at_premium():
    client = ClaudeClient(api_key="k", model="claude-sonnet-5")
    cost = client._calculate_cost(
        input_tokens=0, output_tokens=0, cache_write_tokens=1000
    )
    # cache write billed at 1.25x
    assert cost == (1250 / 1_000_000) * 3.0


def test_total_input_includes_cached_tokens():
    """Usage totals report the full input processed (fresh + cached)."""
    client = ClaudeClient(api_key="k", model="claude-sonnet-5")
    client._track_usage(_usage(100, 50, cache_read=900))
    stats = client.get_usage_stats()
    assert stats["total_input_tokens"] == 1000   # 100 fresh + 900 cached
    assert stats["total_output_tokens"] == 50
