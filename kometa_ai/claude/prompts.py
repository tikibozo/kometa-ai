import logging
import json
from typing import Dict, List, Any

from kometa_ai.radarr.models import Movie
from kometa_ai.kometa.models import CollectionConfig

logger = logging.getLogger(__name__)


def get_system_prompt() -> str:
    """Get the system prompt for Claude.

    Returns:
        System prompt
    """
    return """
You are a film expert tasked with categorizing movies for a Plex media server. Your job is to determine which movies belong in a specific collection based on the provided criteria.

Guidelines:
1. Focus ONLY on the specific collection definition and criteria provided
2. Consider all relevant movie attributes (title, year, genres, plot, directors, actors, etc.)
3. Apply the collection criteria consistently across all movies
4. Provide a confidence score (0.0-1.0) for each decision
5. Include reasoning ONLY for borderline cases (confidence between 0.4-0.8)
6. Return answers in valid JSON format only
7. Do not consider personal preferences or subjective quality judgments

When evaluating movies:
- Be objective and follow the criteria exactly
- Do not artificially limit the number of movies in a collection
- Include a movie if it fits the criteria, regardless of how many you've already included
- Exclude a movie if it doesn't fit the criteria, even if the collection would be empty
- For movies with little information, use your knowledge about films to supplement the data
- Evaluate the movie's actual content and themes, not just what's mentioned in the overview
- Be cautious about superficial similarities and lookout for mismatches between overview and actual film content
- Be discriminating: a movie containing elements of a genre doesn't necessarily mean it belongs in that collection
- Consider the movie's primary themes and genres, not incidental elements

IMPORTANT: For collections based on themes or genres, focus on whether the movie is primarily about that theme/genre, not whether it contains elements of it. For example:
- A movie with one heist scene is not necessarily a "Heist Movie"
- A movie set partly in space is not necessarily a "Space Movie" 
- A movie with some comedy is not necessarily a "Comedy Movie"

Your response must follow this exact JSON format:
{
  "collection_name": "Name of the collection",
  "decisions": [
    {
      "movie_id": 123,
      "title": "Movie Title",
      "include": true,
      "confidence": 0.95,
      "reasoning": "Optional explanation for borderline cases"
    },
    // Additional movies...
  ]
}

IMPORTANT: Return valid JSON only. Do not include markdown formatting or explanatory text outside the JSON structure.
"""


def format_collection_prompt(collection: CollectionConfig) -> str:
    """Format the prompt for a collection.

    Args:
        collection: Collection configuration

    Returns:
        Formatted prompt
    """
    # Log the collection configuration for debugging
    logger.debug(f"Processing collection: {collection.name}")
    logger.debug(f"Collection prompt (type: {type(collection.prompt)}): {repr(collection.prompt)}")
    logger.debug(f"Collection enabled: {collection.enabled}")
    logger.debug(f"Collection confidence: {collection.confidence_threshold}")

    # Ensure the prompt is properly formatted
    formatted_prompt = collection.prompt.strip() if collection.prompt else ""

    # Check for blank prompt
    if not formatted_prompt:
        logger.warning(f"Collection '{collection.name}' has an empty prompt!")

    # More detailed logging for prompt content inspection
    logger.debug(f"Prompt content before formatting (length: {len(formatted_prompt)}):")
    if formatted_prompt:
        # Log each line for debugging bullet points
        for i, line in enumerate(formatted_prompt.split('\n')):
            logger.debug(f"  Prompt line {i}: '{line}'")

    # Create the formatted prompt template
    prompt_template = f"""
I need you to categorize movies for the "{collection.name}" collection.

COLLECTION DEFINITION AND CRITERIA:
{formatted_prompt}

For each movie in the provided list, evaluate whether it belongs in the {collection.name} collection based on these criteria. Provide your decision and a confidence level (0.0-1.0) for each movie.

The minimum confidence threshold for inclusion is {collection.confidence_threshold}. For movies with confidence below this threshold, they will not be included in the collection, so be careful not to underestimate your confidence if you believe a movie should be included.

IMPORTANT CONSIDERATIONS FOR THIS COLLECTION:
- You should only include movies that strongly match the collection's theme/genre
- A movie that contains minor elements or scenes related to the collection theme should NOT be included
- Focus on the movie's primary themes and content, not secondary elements
- When evaluating movies, use your knowledge of cinema to supplement the data provided
- Consider whether a typical viewer would categorize this movie primarily as a {collection.name.rstrip('s')} film

Return your evaluation in the required JSON format ONLY, with no additional text or explanations outside the JSON structure.
"""

    # Log the final formatted prompt for verification
    logger.debug(f"Final formatted prompt length: {len(prompt_template)}")
    logger.debug(f"First 100 chars: {prompt_template[:100]}")
    logger.debug(f"Section with bullet points check: {'-' in formatted_prompt}")
    logger.debug(f"Section with criteria: {'COLLECTION DEFINITION AND CRITERIA:' in prompt_template}")

    # Log the exact content being sent to Claude
    logger.debug("PROMPT CONTENT START >>>")
    logger.debug(prompt_template)
    logger.debug("<<< PROMPT CONTENT END")

    return prompt_template


def format_movies_data(movies: List[Movie]) -> str:
    """Format movie data for Claude prompt.

    Args:
        movies: List of movies

    Returns:
        Formatted movie data
    """
    movies_data = []
    for movie in movies:
        # Create basic movie data
        movie_data = {
            "movie_id": movie.id,
            "title": movie.title,
            "year": movie.year,
            "genres": movie.genres,
            "overview": movie.overview,
        }

        # Add optional metadata if available
        if movie.imdb_id:
            movie_data["imdb_id"] = movie.imdb_id
        if movie.tmdb_id:
            movie_data["tmdb_id"] = movie.tmdb_id
        if movie.studio:
            movie_data["studio"] = movie.studio
        if movie.runtime:
            movie_data["runtime_minutes"] = movie.runtime
        if movie.original_title and movie.original_title != movie.title:
            movie_data["original_title"] = movie.original_title
        if movie.alternative_titles:
            movie_data["alternative_titles"] = [
                title.get('title', '') for title in movie.alternative_titles
            ]
        if movie.collection and 'name' in movie.collection:
            movie_data["collection"] = movie.collection.get('name')

        movies_data.append(movie_data)

    # Return proper JSON string instead of Python string representation
    return json.dumps(movies_data, indent=2)
