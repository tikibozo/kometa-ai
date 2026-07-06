import logging
import json
from typing import Dict, Any, Optional, Tuple, cast
from datetime import datetime, UTC

import anthropic
from anthropic import Anthropic

logger = logging.getLogger(__name__)

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

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a Claude API call in USD."""
        input_rate, output_rate = MODEL_PRICING.get(self.model, DEFAULT_PRICING)
        return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate

    def _track_usage(self, response: anthropic.types.Message) -> Dict[str, Any]:
        """Track API usage for cost monitoring.

        Args:
            response: Claude API response

        Returns:
            Usage stats for this single request
        """
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self._calculate_cost(input_tokens, output_tokens)

        self._cost_tracking['total_input_tokens'] = cast(int, self._cost_tracking['total_input_tokens']) + input_tokens
        self._cost_tracking['total_output_tokens'] = cast(int, self._cost_tracking['total_output_tokens']) + output_tokens
        self._cost_tracking['total_cost'] = cast(float, self._cost_tracking['total_cost']) + cost
        self._cost_tracking['requests'] = cast(int, self._cost_tracking['requests']) + 1

        logger.info(
            f"Claude API usage: {input_tokens} input tokens, "
            f"{output_tokens} output tokens, "
            f"cost: ${cost:.4f}"
        )

        return {
            'total_input_tokens': input_tokens,
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

        user_prompt = f"{collection_prompt}\n\nMOVIES TO EVALUATE:\n{movies_data}"

        response = self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=16000,
            output_config={"format": {"type": "json_schema", "schema": DECISIONS_SCHEMA}},
        )

        usage_stats = self._track_usage(response)

        if self.debug_mode:
            logger.debug(f"Claude response: {response.content}")

        text = next((block.text for block in response.content if block.type == "text"), None)
        if not text:
            raise ValueError(
                f"Claude API returned no text content (stop_reason: {response.stop_reason})"
            )

        parsed_response = json.loads(text)
        if not isinstance(parsed_response.get("decisions"), list):
            raise ValueError("Response missing 'decisions' list")

        return parsed_response, usage_stats
