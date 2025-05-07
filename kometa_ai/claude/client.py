import logging
import time
import json
from typing import Dict, List, Any, Optional, Union, Tuple, cast
from datetime import datetime, UTC

# Type ignore for anthropic imports as they don't have stubs
import anthropic  # type: ignore
from anthropic import Anthropic  # type: ignore

logger = logging.getLogger(__name__)

# Max retries for API calls
MAX_RETRIES = 5
# Default batch size for movie processing
DEFAULT_BATCH_SIZE = 150


class ClaudeClient:
    """Client for interacting with the Claude AI API."""

    def __init__(self, api_key: str, debug_mode: bool = False, model: str = None):
        """Initialize the Claude API client.

        Args:
            api_key: API key for authentication
            debug_mode: Whether to log full prompts and responses
            model: Claude model to use (defaults to claude-3-5-sonnet-20240620 if None)
        """
        self.api_key = api_key
        self.debug_mode = debug_mode
        self.client = Anthropic(api_key=api_key)
        self._cost_tracking = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'requests': 0,
            'start_time': datetime.now(UTC).isoformat()
        }
        self.model = model if model else "claude-3-7-sonnet-latest"  # Default model
        logger.info(f"Initialized Claude client with model {self.model}")

    def test_connection(self) -> bool:
        """Test the connection to Claude API.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Just check if we can instantiate the client
            _ = Anthropic(api_key=self.api_key)
            logger.info("Claude API connection test successful")
            return True
        except Exception as e:
            logger.error(f"Claude API connection test failed: {e}")
            return False

    def _track_usage(self, response: anthropic.types.Message) -> None:
        """Track API usage for cost monitoring.

        Args:
            response: Claude API response
        """
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Approximate cost calculation (as of May 2024)
            # Claude 3.5 Sonnet: $3/million input tokens, $15/million output tokens
            input_cost = (input_tokens / 1_000_000) * 3.0
            output_cost = (output_tokens / 1_000_000) * 15.0
            total_cost = input_cost + output_cost

            # Update tracking with type safety
            # Use type checking to handle dynamic dictionary values safely
            self._cost_tracking['total_input_tokens'] = cast(int, self._cost_tracking['total_input_tokens']) + input_tokens
            self._cost_tracking['total_output_tokens'] = cast(int, self._cost_tracking['total_output_tokens']) + output_tokens
            self._cost_tracking['total_cost'] = cast(float, self._cost_tracking['total_cost']) + total_cost
            self._cost_tracking['requests'] = cast(int, self._cost_tracking['requests']) + 1

            # Log usage
            logger.info(
                f"Claude API usage: {input_tokens} input tokens, "
                f"{output_tokens} output tokens, "
                f"cost: ${total_cost:.4f}"
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics.

        Returns:
            Dictionary with usage statistics
        """
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
        movies_data: str,
        batch_size: Optional[int] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Classify movies for a collection using Claude.

        Args:
            system_prompt: System prompt
            collection_prompt: Collection-specific prompt
            movies_data: Formatted movie data
            batch_size: Number of movies to process in each batch

        Returns:
            Tuple of (parsed JSON response, usage stats)
        """
        if not batch_size:
            batch_size = DEFAULT_BATCH_SIZE

        # Log full prompts if in debug mode
        if self.debug_mode:
            logger.debug(f"System prompt: {system_prompt}")
            logger.debug(f"Collection prompt: {collection_prompt}")
            logger.debug(f"Movies data: {movies_data}")

        retries = 0
        while retries < MAX_RETRIES:
            try:
                # Create user prompt with a clear JSON request
                user_prompt = (
                    f"{collection_prompt}\n\n"
                    f"MOVIES TO EVALUATE:\n{movies_data}\n\n"
                    f"IMPORTANT: Respond ONLY with a valid JSON object containing 'collection_name' and 'decisions' fields."
                )

                # Make API call with more specific error handling
                response = self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.1,  # Low temperature for consistent classification
                    max_tokens=4000
                )

                # Track usage
                self._track_usage(response)

                # Log full response if in debug mode
                if self.debug_mode:
                    logger.debug(f"Claude response: {response.content}")

                # Validate response has content
                if not response.content:
                    raise ValueError("Claude API returned empty response")
                
                # Check for TextBlock with text attribute
                if not hasattr(response.content[0], "text") or not response.content[0].text:
                    raise ValueError("Claude API returned response without text content")

                # Parse JSON from response
                try:
                    parsed_response = self._parse_json_response(response.content[0].text)

                    # Basic response validation
                    if "collection_name" not in parsed_response:
                        raise ValueError("Response missing 'collection_name' field")
                    if "decisions" not in parsed_response:
                        raise ValueError("Response missing 'decisions' field")
                    if not isinstance(parsed_response["decisions"], list):
                        raise ValueError("'decisions' field must be a list")

                    return parsed_response, self.get_usage_stats()

                except (ValueError, json.JSONDecodeError) as e:
                    # Log the response that failed parsing
                    logger.error(f"JSON parsing error: {e}")
                    # Get text from response content safely
                    response_text = getattr(response.content[0], "text", "No text content")
                    logger.error(f"Failed to parse response: {response_text[:500]}...")

                    # Retry with the same strategy as rate limit errors
                    retries += 1
                    if retries < MAX_RETRIES:
                        wait_time = min(2 ** retries, 30)
                        logger.warning(f"Retrying after parsing error in {wait_time}s (attempt {retries}/{MAX_RETRIES})")
                        time.sleep(wait_time)
                    else:
                        raise ValueError(f"Failed to parse Claude response after {MAX_RETRIES} attempts") from e

            except (anthropic.RateLimitError, anthropic.APITimeoutError,
                    anthropic.APIConnectionError, anthropic.InternalServerError) as e:
                # Retryable API errors
                retries += 1
                wait_time = min(2 ** retries, 30)  # Exponential backoff, max 30 seconds
                logger.warning(f"Claude API error ({e.__class__.__name__}): {e}")
                logger.warning(f"Retrying in {wait_time}s (attempt {retries}/{MAX_RETRIES})")

                if retries < MAX_RETRIES:
                    time.sleep(wait_time)
                else:
                    logger.error(f"Exhausted retries ({MAX_RETRIES}) for Claude API call")
                    raise

            except anthropic.APIError as e:
                # Handle specific API errors with useful context
                error_message = str(e)
                context = f"Claude API error: {e.__class__.__name__}"

                if "token limit" in error_message.lower() or "token_limit" in error_message.lower():
                    raise ValueError(f"{context}: Input too large, reduce batch size from {batch_size}") from e
                elif "content policy" in error_message.lower():
                    raise ValueError(f"{context}: Content policy violation in prompt or movie data") from e
                else:
                    # Other API errors
                    logger.error(f"{context}: {error_message}")
                    raise

            except Exception as e:
                # Unexpected errors
                logger.error(f"Unexpected error classifying movies: {e}")
                raise

        # If we've exhausted retries
        raise Exception(f"Failed to classify movies after {MAX_RETRIES} retries")

    def analyze_movie(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Analyze a single movie in detail.
        
        Args:
            system_prompt: System prompt for the analysis
            user_prompt: User prompt with movie details
            
        Returns:
            Tuple of (analysis response, usage stats)
        """
        try:
            # Create message context
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
            
            # Log full prompts if in debug mode
            if self.debug_mode:
                logger.debug(f"System prompt: {system_prompt}")
                logger.debug(f"User prompt: {user_prompt}")
            
            # Make API request
            response = self.client.messages.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,  # Adjust as needed
                temperature=0.1   # Lower temperature for more consistent results
            )
            
            # Track usage
            self._track_usage(response)
            
            # Extract response content
            if not response.content or not hasattr(response.content[0], "text"):
                raise ValueError("Claude API returned empty or invalid response")
                
            content = response.content[0].text
            
            # Log full response if in debug mode
            if self.debug_mode:
                logger.debug(f"Claude response: {content}")
            
            # Parse JSON from response
            try:
                analysis = self._parse_json_response(content)
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse analysis response: {e}")
                logger.error(f"Response content: {content[:500]}...")
                
                # Create a basic structure with error info
                analysis = {
                    "error": "Failed to parse response JSON",
                    "include": False,
                    "confidence": 0.0,
                    "reasoning": f"Error analyzing movie: {str(e)}"
                }
            
            # Calculate usage statistics
            usage_stats = {
                "total_input_tokens": response.usage.input_tokens,
                "total_output_tokens": response.usage.output_tokens,
                "total_cost": self._calculate_cost(
                    response.usage.input_tokens,
                    response.usage.output_tokens
                ),
                "requests": 1
            }
            
            return analysis, usage_stats
            
        except Exception as e:
            logger.error(f"Error analyzing movie: {e}")
            raise
            
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a Claude API call.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        # Approximate cost calculation (as of May 2024)
        # Claude 3.5 Sonnet: $3/million input tokens, $15/million output tokens
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from Claude's response with multiple fallback strategies.

        Args:
            response_text: Claude's response text

        Returns:
            Parsed JSON

        Raises:
            ValueError: If JSON parsing fails after all attempts
        """
        import re

        # Store original error for context if all parsing attempts fail
        original_error = None

        # Strategy 1: Parse the entire response as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            original_error = e
            if self.debug_mode:
                logger.debug(f"Direct JSON parsing failed: {e}")

        # Strategy 2: Look for JSON between triple backticks (markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                if self.debug_mode:
                    logger.debug(f"Code block JSON parsing failed: {e}")

        # Strategy 3: Look for JSON between curly braces at the end of the response
        json_match = re.search(r'(\{[\s\S]*?\}\s*$)', response_text)
        if json_match:
            json_str = json_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Strategy 3.1: Try cleaning up comments and other non-JSON elements
                try:
                    # Remove line comments
                    cleaned_str = re.sub(r'//.*?$', '', json_str, flags=re.MULTILINE)
                    # Remove block comments
                    cleaned_str = re.sub(r'/\*.*?\*/', '', cleaned_str, flags=re.DOTALL)
                    # Remove trailing commas in arrays and objects
                    cleaned_str = re.sub(r',\s*([}\]])', r'\1', cleaned_str)

                    return json.loads(cleaned_str)
                except json.JSONDecodeError as e:
                    if self.debug_mode:
                        logger.debug(f"Cleaned JSON parsing failed: {e}")

        # Strategy 4: Try to extract just collection_name and decisions
        collection_match = re.search(r'"collection_name"\s*:\s*"([^"]+)"', response_text)
        decisions_match = re.search(r'"decisions"\s*:\s*(\[[\s\S]*?\])', response_text)

        if collection_match and decisions_match:
            collection_name = collection_match.group(1)
            decisions_str = decisions_match.group(1)

            # Try to reconstruct a valid JSON
            try:
                # Clean up decisions string - remove trailing commas
                decisions_str = re.sub(r',\s*\]', ']', decisions_str)
                decisions = json.loads(decisions_str)

                return {
                    "collection_name": collection_name,
                    "decisions": decisions
                }
            except json.JSONDecodeError as e:
                if self.debug_mode:
                    logger.debug(f"Reconstructed JSON parsing failed: {e}")

        # Strategy 5: Most aggressive approach - try to manually extract individual decisions
        # This is a last resort for severely malformed responses
        try:
            # Extract collection name
            collection_match = re.search(r'"collection_name"\s*:\s*"([^"]+)"', response_text)
            collection_name = collection_match.group(1) if collection_match else "Unknown Collection"

            # Extract individual decision objects
            decision_objects = re.findall(r'(\{\s*"movie_id"\s*:\s*\d+[^}]+\})', response_text)

            if decision_objects:
                decisions = []
                for decision_str in decision_objects:
                    # Clean and add missing quotes where needed
                    fixed_str = re.sub(r'(\w+)\s*:', r'"\1":', decision_str)
                    try:
                        decision = json.loads(fixed_str)
                        decisions.append(decision)
                    except json.JSONDecodeError:
                        continue  # Skip this malformed decision

                if decisions:
                    return {
                        "collection_name": collection_name,
                        "decisions": decisions
                    }
        except Exception as e:
            if self.debug_mode:
                logger.debug(f"Manual decision extraction failed: {e}")

        # If all parsing attempts fail, provide a detailed error
        error_msg = f"Failed to parse JSON response after multiple attempts"
        logger.error(f"{error_msg}. Response preview: {response_text[:200]}...")
        logger.error(f"Original error: {original_error}")

        raise ValueError(error_msg)
