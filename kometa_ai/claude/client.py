import logging
import json
from typing import Dict, Any, Optional, Protocol, Tuple, cast
from datetime import datetime, UTC

import anthropic
from anthropic import Anthropic
from anthropic.types import TextBlockParam

logger = logging.getLogger(__name__)


class ClaudeUsageLimitError(RuntimeError):
    """Raised when Claude declines further work because a usage/rate limit is
    hit. This is a whole-run condition, not a per-batch one: every subsequent
    request will fail the same way until the window resets, so the caller
    should stop processing rather than hammer the remaining batches."""


class ClaudeBackend(Protocol):
    """The contract both Claude backends (API and CLI) must satisfy."""

    model: str

    def classify_movies(
        self, system_prompt: str, collection_prompt: str, movies_data: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]: ...

    def get_usage_stats(self) -> Dict[str, Any]: ...

    def reset_usage_stats(self) -> None: ...


DEFAULT_MODEL = "claude-sonnet-5"
# Default batch size for movie processing
DEFAULT_BATCH_SIZE = 150

# USD per million tokens (input, output)
MODEL_PRICING = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
DEFAULT_PRICING = (3.0, 15.0)

# JSON schema enforced via structured outputs. Property order matters:
# reasoning comes before include/confidence so the model commits to its
# analysis before the verdict.
DECISIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "collection_name": {"type": "string"},
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "movie_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "include": {"type": "boolean"},
                    "confidence": {"type": "number"},
                },
                "required": ["movie_id", "include", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["collection_name", "decisions"],
    "additionalProperties": False,
}


class ClaudeClient:
    """Client for interacting with the Claude AI API."""

    def __init__(self, api_key: str, debug_mode: bool = False, model: Optional[str] = None):
        """Initialize the Claude API client.

        Args:
            api_key: API key for authentication
            debug_mode: Whether to log full prompts and responses
            model: Claude model to use (defaults to DEFAULT_MODEL if None)
        """
        self.api_key = api_key
        self.debug_mode = debug_mode
        # The SDK retries rate limits and server errors with backoff
        self.client = Anthropic(api_key=api_key, max_retries=5)
        self._cost_tracking = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'start_time': datetime.now(UTC).isoformat()
        }
        self.model = model if model else DEFAULT_MODEL
        logger.info(f"Initialized Claude client with model {self.model}")

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """Calculate the cost of a Claude API call in USD.

        Prompt-cache tokens (Lever 5) are billed at Anthropic's published
        multiples of the base input rate: a cache write costs 1.25x and a cache
        read 0.1x. Fresh (uncached) input is billed at 1x.
        """
        input_rate, output_rate = MODEL_PRICING.get(self.model, DEFAULT_PRICING)
        billable_input = (
            input_tokens
            + cache_write_tokens * 1.25
            + cache_read_tokens * 0.1
        )
        return (billable_input / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate

    def _track_usage(self, response: anthropic.types.Message) -> Dict[str, Any]:
        """Track API usage for cost monitoring.

        Args:
            response: Claude API response

        Returns:
            Usage stats for this single request
        """
        usage = response.usage
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        # Present on responses that hit the prompt cache; absent (None) otherwise
        cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
        cache_write = getattr(usage, 'cache_creation_input_tokens', 0) or 0
        cost = self._calculate_cost(input_tokens, output_tokens, cache_read, cache_write)

        # Report the full input size (fresh + cached) so the usage summary
        # reflects everything processed, not just the uncached remainder.
        total_input = input_tokens + cache_read + cache_write

        self._cost_tracking['total_input_tokens'] = cast(int, self._cost_tracking['total_input_tokens']) + total_input
        self._cost_tracking['total_output_tokens'] = cast(int, self._cost_tracking['total_output_tokens']) + output_tokens
        self._cost_tracking['total_cost'] = cast(float, self._cost_tracking['total_cost']) + cost
        self._cost_tracking['requests'] = cast(int, self._cost_tracking['requests']) + 1

        cache_note = f", {cache_read} cached" if cache_read else ""
        logger.info(
            f"Claude API usage: {input_tokens} input tokens{cache_note}, "
            f"{output_tokens} output tokens, "
            f"cost: ${cost:.4f}"
        )

        return {
            'total_input_tokens': total_input,
            'total_output_tokens': output_tokens,
            'total_cost': cost,
            'requests': 1,
        }

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

    def classify_movies(
        self,
        system_prompt: str,
        collection_prompt: str,
        movies_data: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Classify movies for a collection using Claude.

        Args:
            system_prompt: System prompt
            collection_prompt: Collection-specific prompt
            movies_data: Formatted movie data

        Returns:
            Tuple of (parsed decisions response, usage stats for this request)
        """
        if self.debug_mode:
            logger.debug(f"System prompt: {system_prompt}")
            logger.debug(f"Collection prompt: {collection_prompt}")
            logger.debug(f"Movies data: {movies_data}")

        # Lever 5 — prompt caching. The system prompt is identical across every
        # collection and run; the collection prompt is identical across every
        # batch of one collection. Mark both as cache breakpoints so batches
        # after the first reuse the cached prefix and only the per-batch movie
        # data (and output) are billed at full rate. The ephemeral cache's
        # ~5-minute TTL is refreshed on each read, so it stays warm as long as
        # batches run back-to-back.
        system_blocks: list[TextBlockParam] = [{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }]
        user_content: list[TextBlockParam] = [
            {
                "type": "text",
                "text": collection_prompt,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": f"MOVIES TO EVALUATE:\n{movies_data}",
            },
        ]

        # Stream so the large max_tokens doesn't hit SDK HTTP timeouts; the
        # cap leaves headroom for per-movie reasoning on a full batch
        try:
            with self.client.messages.stream(
                model=self.model,
                system=system_blocks,
                messages=[{"role": "user", "content": user_content}],
                max_tokens=32000,
                output_config={"format": {"type": "json_schema", "schema": DECISIONS_SCHEMA}},
            ) as stream:
                response = stream.get_final_message()
        except anthropic.RateLimitError as e:
            # A 429 is a whole-run condition, same as the CLI backend's usage
            # limit: let the processor stop rather than hammer every batch.
            raise ClaudeUsageLimitError(f"Claude API rate limit reached: {e}") from e

        usage_stats = self._track_usage(response)

        if self.debug_mode:
            logger.debug(f"Claude response: {response.content}")

        if response.stop_reason == "max_tokens":
            # Truncated JSON would fail identically on every run (batches are
            # deterministic) — surface the actionable fix instead
            raise ValueError(
                "Claude response hit the max_tokens cap and is truncated; "
                "reduce --batch-size for this library"
            )

        text = next((block.text for block in response.content if block.type == "text"), None)
        if not text:
            raise ValueError(
                f"Claude API returned no text content (stop_reason: {response.stop_reason})"
            )

        parsed_response = json.loads(text)
        if not isinstance(parsed_response.get("decisions"), list):
            raise ValueError("Response missing 'decisions' list")

        return parsed_response, usage_stats
