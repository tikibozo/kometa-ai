import logging
import json
import re
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, UTC

from kometa_ai.claude.client import DEFAULT_MODEL

logger = logging.getLogger(__name__)

# A full batch (150 movies) can take several minutes to evaluate
CLI_TIMEOUT_SECONDS = 900


class ClaudeCliClient:
    """Drop-in ClaudeClient replacement that shells out to the Claude Code CLI.

    Uses whatever credentials the CLI is logged in with — typically a
    Claude subscription (OAuth), so runs don't bill against an API key.
    Unlike the API backend, the CLI can't enforce a JSON schema server-side,
    so responses are prompt-enforced JSON with a lenient parse and one retry.
    """

    def __init__(self, debug_mode: bool = False, model: Optional[str] = None,
                 claude_bin: str = "claude"):
        """Initialize the CLI client.

        Args:
            debug_mode: Whether to log full prompts and responses
            model: Claude model to use (defaults to DEFAULT_MODEL if None)
            claude_bin: Path to the claude CLI binary
        """
        self.debug_mode = debug_mode
        self.model = model if model else DEFAULT_MODEL
        self.claude_bin = claude_bin
        self._cost_tracking: Dict[str, Any] = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'start_time': datetime.now(UTC).isoformat()
        }
        logger.info(f"Initialized Claude CLI client with model {self.model}")

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get cumulative usage statistics for this client."""
        stats = self._cost_tracking.copy()
        stats['end_time'] = datetime.now(UTC).isoformat()
        return stats

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self._cost_tracking = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'start_time': datetime.now(UTC).isoformat()
        }

    def _run_cli(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """Run one claude -p invocation and return the parsed result envelope."""
        cmd = [
            self.claude_bin,
            "-p",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt", system_prompt,
            "--no-session-persistence",
            "--tools", "",
        ]

        if self.debug_mode:
            logger.debug(f"CLI command: {' '.join(cmd[:6])} ...")
            logger.debug(f"User prompt: {user_prompt[:2000]}")

        result = subprocess.run(
            cmd,
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=CLI_TIMEOUT_SECONDS,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}"
            )

        envelope = json.loads(result.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude CLI returned error: {envelope.get('result', '')[:500]}")
        return envelope

    def _track_usage(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Record usage from a CLI result envelope; returns per-request stats."""
        usage = envelope.get("usage") or {}
        input_tokens = (usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0))
        output_tokens = usage.get("output_tokens", 0)
        # Subscription runs report no marginal cost; API-key CLI runs do
        cost = envelope.get("total_cost_usd") or 0.0

        self._cost_tracking['total_input_tokens'] += input_tokens
        self._cost_tracking['total_output_tokens'] += output_tokens
        self._cost_tracking['total_cost'] += cost
        self._cost_tracking['requests'] += 1

        logger.info(
            f"Claude CLI usage: {input_tokens} input tokens, {output_tokens} output tokens"
            + (f", cost: ${cost:.4f}" if cost else " (subscription)")
        )

        return {
            'total_input_tokens': input_tokens,
            'total_output_tokens': output_tokens,
            'total_cost': cost,
            'requests': 1,
        }

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object from CLI output, tolerating a code fence."""
        text = text.strip()
        fenced = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if fenced:
            text = fenced.group(1)
        start = text.find('{')
        if start > 0:
            text = text[start:]
        return json.loads(text)

    def classify_movies(
        self,
        system_prompt: str,
        collection_prompt: str,
        movies_data: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Classify movies for a collection using the Claude CLI.

        Args:
            system_prompt: System prompt
            collection_prompt: Collection-specific prompt
            movies_data: Formatted movie data

        Returns:
            Tuple of (parsed decisions response, usage stats for this request)
        """
        json_instruction = (
            "Respond with ONLY a JSON object — no prose, no markdown fence — in this shape:\n"
            '{"collection_name": "...", "decisions": [{"movie_id": 123, "title": "...", '
            '"reasoning": "...", "include": true, "confidence": 0.95}, ...]}\n'
            "Include one decision per movie. Write reasoning before include/confidence."
        )
        user_prompt = (
            f"{collection_prompt}\n\n"
            f"MOVIES TO EVALUATE:\n{movies_data}\n\n"
            f"{json_instruction}"
        )

        usage_totals: List[Dict[str, Any]] = []
        last_error: Optional[Exception] = None
        for attempt in range(2):
            envelope = self._run_cli(system_prompt, user_prompt)
            usage_totals.append(self._track_usage(envelope))

            try:
                parsed = self._parse_json(envelope.get("result", ""))
                if not isinstance(parsed.get("decisions"), list):
                    raise ValueError("Response missing 'decisions' list")

                usage = {
                    'total_input_tokens': sum(u['total_input_tokens'] for u in usage_totals),
                    'total_output_tokens': sum(u['total_output_tokens'] for u in usage_totals),
                    'total_cost': sum(u['total_cost'] for u in usage_totals),
                    'requests': len(usage_totals),
                }
                return parsed, usage
            except (ValueError, json.JSONDecodeError) as e:
                last_error = e
                logger.warning(f"CLI response parse failed (attempt {attempt + 1}/2): {e}")

        raise ValueError(f"Failed to parse Claude CLI response: {last_error}")
