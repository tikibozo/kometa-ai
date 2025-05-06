import logging
import requests  # type: ignore
import time
from typing import List, Dict, Any, Optional, Union, Tuple

from kometa_ai.radarr.models import Movie, Tag

logger = logging.getLogger(__name__)


class RadarrClient:
    """Client for interacting with the Radarr API."""

    def __init__(self, base_url: str, api_key: str, max_retries: int = 5):
        """Initialize the Radarr API client.

        Args:
            base_url: Base URL of the Radarr instance
            api_key: API key for authentication
            max_retries: Maximum number of retries on failure
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Kometa-AI',
            'Accept': 'application/json',
            'X-Api-Key': api_key,  # Radarr uses header-based auth by default
        })

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> requests.Response:
        """Make a request to the Radarr API with retry logic and detailed error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            data: Form data
            json_data: JSON data
            retry_count: Current retry count

        Returns:
            Response object

        Raises:
            requests.RequestException: On API error after max retries
            ValueError: For validation errors or invalid requests
        """
        # Standardize on v3 API
        if endpoint.startswith('/api/'):
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
        else:
            url = f"{self.base_url}/api/v3/{endpoint.lstrip('/')}"

        if params is None:
            params = {}

        # Ensure headers are properly set for every request
        headers = {
            'X-Api-Key': self.api_key,
            'Accept': 'application/json',
            'User-Agent': 'Kometa-AI'
        }

        try:
            # Log the request at debug level
            if logger.isEnabledFor(logging.DEBUG):
                debug_info = f"{method} {url}"
                if json_data:
                    debug_info += f" with payload: {json_data}"
                logger.debug(debug_info)

            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=headers,  # Explicitly add headers to every request
                timeout=30  # 30 second timeout
            )

            # Handle specific error status codes
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get('message', str(error_data))
                except (ValueError, KeyError):
                    error_message = response.text

                if response.status_code == 400:
                    # Bad request - likely a validation error
                    logger.error(f"Validation error with Radarr API: {error_message}")
                    raise ValueError(f"Radarr validation error: {error_message}")
                elif response.status_code == 401:
                    # Authentication error
                    logger.error("Authentication failed with Radarr API - check your API key")
                    raise ValueError("Radarr authentication failed - invalid API key")
                elif response.status_code == 404:
                    # Not found
                    logger.error(f"Resource not found: {url}")
                    raise ValueError(f"Radarr resource not found: {endpoint}")
                elif response.status_code == 409:
                    # Conflict - e.g., trying to add a duplicate tag
                    logger.error(f"Conflict with Radarr API: {error_message}")
                    raise ValueError(f"Radarr conflict error: {error_message}")

                # Let requests handle other status codes
                response.raise_for_status()

            return response

        except (requests.ConnectionError, requests.Timeout) as e:
            # Network-related errors that are definitely retryable
            if retry_count >= self.max_retries:
                logger.error(f"Radarr API connection failed after {self.max_retries} retries: {str(e)}")
                raise ValueError(f"Cannot connect to Radarr at {self.base_url}: {str(e)}") from e

            # Calculate backoff time (exponential with jitter)
            backoff = min(2 ** retry_count + (retry_count * 0.1), 30)
            logger.warning(f"Radarr API connection error, retrying in {backoff:.2f} seconds: {str(e)}")
            time.sleep(backoff)

            return self._make_request(
                method, endpoint, params, data, json_data, retry_count + 1
            )

        except requests.RequestException as e:
            # Other request errors
            if retry_count >= self.max_retries:
                logger.error(f"Radarr API request failed after {self.max_retries} retries: {str(e)}")

                # Create a more descriptive error message
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_data = e.response.json()
                        error_message = error_data.get('message', str(error_data))
                    except (ValueError, KeyError):
                        error_message = e.response.text or str(e)
                else:
                    error_message = str(e)

                raise ValueError(f"Radarr API error: {error_message}") from e

            # Calculate backoff time (exponential with jitter)
            backoff = min(2 ** retry_count + (retry_count * 0.1), 30)
            logger.warning(f"Radarr API request failed, retrying in {backoff:.2f} seconds: {str(e)}")
            time.sleep(backoff)

            return self._make_request(
                method, endpoint, params, data, json_data, retry_count + 1
            )

    def get_movies(self) -> List[Movie]:
        """Get all movies from Radarr.

        Returns:
            List of movies
        """
        logger.debug("Making API request to fetch movies from Radarr")
        response = self._make_request('GET', '/movie')
        movies_data = response.json()

        logger.info(f"Fetched {len(movies_data)} movies from Radarr")
        return [Movie.from_dict(movie_data) for movie_data in movies_data]

    def get_movie(self, movie_id: int) -> Movie:
        """Get a movie by ID.

        Args:
            movie_id: Movie ID

        Returns:
            Movie object

        Raises:
            requests.RequestException: If the movie is not found
        """
        logger.debug(f"Fetching movie {movie_id} from Radarr")
        response = self._make_request('GET', f'/movie/{movie_id}')
        movie_data = response.json()

        return Movie.from_dict(movie_data)

    def get_tags(self) -> List[Tag]:
        """Get all tags from Radarr.

        Returns:
            List of tags
        """
        logger.info("Fetching tags from Radarr")
        response = self._make_request('GET', '/tag')
        tags_data = response.json()

        logger.info(f"Fetched {len(tags_data)} tags from Radarr")
        return [Tag.from_dict(tag_data) for tag_data in tags_data]

    def get_tag_by_label(self, label: str) -> Optional[Tag]:
        """Get a tag by its label.

        Args:
            label: Tag label

        Returns:
            Tag object or None if not found
        """
        tags = self.get_tags()
        for tag in tags:
            if tag.label.lower() == label.lower():
                return tag
        return None

    def create_tag(self, label: str) -> Tag:
        """Create a new tag.

        Args:
            label: Tag label

        Returns:
            Created tag
        """
        logger.info(f"Creating tag '{label}' in Radarr")
        response = self._make_request('POST', '/tag', json_data={'label': label})
        tag_data = response.json()

        return Tag.from_dict(tag_data)

    def get_or_create_tag(self, label: str) -> Tag:
        """Get a tag by label or create it if it doesn't exist.

        Args:
            label: Tag label

        Returns:
            Tag object
        """
        existing_tag = self.get_tag_by_label(label)
        if existing_tag:
            return existing_tag

        return self.create_tag(label)

    def update_movie(self, movie: Movie) -> Movie:
        """Update a movie in Radarr.

        Args:
            movie: Movie object to update

        Returns:
            Updated movie object

        Raises:
            requests.RequestException: If the update fails
        """
        logger.info(f"Updating movie {movie.id} in Radarr")
        movie_data = movie.to_dict()
        response = self._make_request('PUT', f'/movie/{movie.id}', json_data=movie_data)
        updated_movie_data = response.json()

        logger.debug(f"Successfully updated movie {movie.id} in Radarr")
        return Movie.from_dict(updated_movie_data)

    def update_movie_tags(self, movie_id: int, tag_ids: List[int]) -> Movie:
        """Update the tags for a movie.

        Args:
            movie_id: Movie ID
            tag_ids: List of tag IDs to set

        Returns:
            Updated movie object

        Raises:
            requests.RequestException: If the update fails
        """
        logger.info(f"Updating tags for movie {movie_id}")
        movie = self.get_movie(movie_id)

        # Only update if tags have changed
        if set(movie.tag_ids) != set(tag_ids):
            logger.debug(f"Changing tags for movie {movie_id} from {movie.tag_ids} to {tag_ids}")
            movie.tag_ids = tag_ids
            return self.update_movie(movie)
        else:
            logger.debug(f"Tags for movie {movie_id} are already set to {tag_ids}, skipping update")
            return movie

    def add_tag_to_movie(self, movie_id: int, tag_id: int) -> Movie:
        """Add a tag to a movie.

        Args:
            movie_id: Movie ID
            tag_id: Tag ID to add

        Returns:
            Updated movie object

        Raises:
            requests.RequestException: If the update fails
        """
        movie = self.get_movie(movie_id)
        if tag_id not in movie.tag_ids:
            movie.tag_ids.append(tag_id)
            return self.update_movie(movie)
        return movie

    def remove_tag_from_movie(self, movie_id: int, tag_id: int) -> Movie:
        """Remove a tag from a movie.

        Args:
            movie_id: Movie ID
            tag_id: Tag ID to remove

        Returns:
            Updated movie object

        Raises:
            requests.RequestException: If the update fails
        """
        movie = self.get_movie(movie_id)
        if tag_id in movie.tag_ids:
            movie.tag_ids.remove(tag_id)
            return self.update_movie(movie)
        return movie

    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag from Radarr.

        Args:
            tag_id: Tag ID to delete

        Returns:
            True if the tag was deleted successfully

        Raises:
            requests.RequestException: If the delete fails
        """
        logger.info(f"Deleting tag {tag_id} from Radarr")
        self._make_request('DELETE', f'/tag/{tag_id}')
        logger.debug(f"Successfully deleted tag {tag_id}")
        return True

    def update_tag(self, tag: Tag) -> Tag:
        """Update a tag in Radarr.

        Args:
            tag: Tag object to update

        Returns:
            Updated tag object

        Raises:
            requests.RequestException: If the update fails
        """
        logger.info(f"Updating tag {tag.id} in Radarr")
        response = self._make_request('PUT', f'/tag/{tag.id}', json_data={'id': tag.id, 'label': tag.label})
        tag_data = response.json()

        logger.debug(f"Successfully updated tag {tag.id}")
        return Tag.from_dict(tag_data)

    def test_connection(self) -> bool:
        """Test the connection to Radarr API with detailed diagnostics.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            logger.info(f"Testing connection to Radarr API at {self.base_url}")
            response = self._make_request('GET', '/system/status')
            data = response.json()
            logger.info(f"Successfully connected to Radarr API (version: {data.get('version', 'unknown')})")
            return True
        except ValueError as ve:
            # These are expected formatting errors
            logger.error(f"Failed to connect to Radarr API: {str(ve)}")
            return False
        except Exception as e:
            # Log more detailed error information for connection issues
            import socket
            from urllib.parse import urlparse

            # Try to provide more diagnostic information
            url_parts = urlparse(self.base_url)
            host = url_parts.hostname
            port = url_parts.port or (443 if url_parts.scheme == 'https' else 80)

            # Test direct connection to host without HTTP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                result = s.connect_ex((host, port))
                if result == 0:
                    logger.error(f"TCP connection to {host}:{port} succeeded, but HTTP request failed: {str(e)}")
                else:
                    logger.error(f"TCP connection to {host}:{port} failed (errno: {result}): {str(e)}")
                s.close()
            except Exception as sock_err:
                logger.error(f"Could not test TCP connection to {host}:{port}: {str(sock_err)}")

            return False
