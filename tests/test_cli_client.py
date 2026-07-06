"""Tests for the Claude CLI backend and backend selection."""

import json
from unittest.mock import patch, MagicMock

import pytest

from kometa_ai.claude.cli_client import ClaudeCliClient
from kometa_ai.claude.client import ClaudeClient
from kometa_ai.__main__ import make_claude_client


def make_envelope(result_text, input_tokens=100, output_tokens=50, cost=0.0):
    return json.dumps({
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": result_text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        "total_cost_usd": cost,
    })


def run_result(stdout, returncode=0, stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


DECISIONS = '{"collection_name": "Test", "decisions": [{"movie_id": 1, "include": true, "confidence": 0.9}]}'


class TestClaudeCliClient:
    def test_classify_movies_parses_plain_json(self):
        client = ClaudeCliClient()
        with patch("subprocess.run", return_value=run_result(make_envelope(DECISIONS))) as mock_run:
            response, usage = client.classify_movies("system", "collection", "[]")

        assert response["decisions"][0]["movie_id"] == 1
        assert usage["requests"] == 1
        assert usage["total_input_tokens"] == 100

        cmd = mock_run.call_args.args[0]
        assert "-p" in cmd
        assert "--output-format" in cmd
        assert mock_run.call_args.kwargs["input"].startswith("collection")

    def test_classify_movies_tolerates_code_fence(self):
        fenced = f"```json\n{DECISIONS}\n```"
        client = ClaudeCliClient()
        with patch("subprocess.run", return_value=run_result(make_envelope(fenced))):
            response, _ = client.classify_movies("system", "collection", "[]")
        assert response["decisions"][0]["include"] is True

    def test_classify_movies_retries_once_on_garbage(self):
        client = ClaudeCliClient()
        results = [
            run_result(make_envelope("I can't produce JSON right now.")),
            run_result(make_envelope(DECISIONS)),
        ]
        with patch("subprocess.run", side_effect=results) as mock_run:
            response, usage = client.classify_movies("system", "collection", "[]")

        assert mock_run.call_count == 2
        assert usage["requests"] == 2
        assert response["collection_name"] == "Test"

    def test_cli_failure_raises(self):
        client = ClaudeCliClient()
        with patch("subprocess.run", return_value=run_result("", returncode=1, stderr="not logged in")):
            with pytest.raises(RuntimeError, match="not logged in"):
                client.classify_movies("system", "collection", "[]")

    def test_usage_accumulates(self):
        client = ClaudeCliClient()
        with patch("subprocess.run", return_value=run_result(make_envelope(DECISIONS, cost=0.01))):
            client.classify_movies("system", "collection", "[]")
            client.classify_movies("system", "collection", "[]")
        stats = client.get_usage_stats()
        assert stats["requests"] == 2
        assert stats["total_cost"] == pytest.approx(0.02)


class TestBackendSelection:
    def test_default_is_api(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_API_KEY", "k")
        monkeypatch.delenv("CLAUDE_BACKEND", raising=False)
        assert isinstance(make_claude_client(), ClaudeClient)

    def test_cli_backend(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_BACKEND", "cli")
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
        with patch("shutil.which", return_value="/usr/local/bin/claude"):
            assert isinstance(make_claude_client(), ClaudeCliClient)

    def test_cli_backend_requires_binary(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_BACKEND", "cli")
        with patch("shutil.which", return_value=None):
            assert make_claude_client() is None

    def test_api_backend_requires_key(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_BACKEND", "api")
        monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
        assert make_claude_client() is None

    def test_unknown_backend_rejected(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_BACKEND", "carrier-pigeon")
        assert make_claude_client() is None
