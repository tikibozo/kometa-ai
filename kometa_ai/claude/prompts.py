import logging
import json
from typing import Dict, List, Optional

from kometa_ai.radarr.models import Movie
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.state.models import DecisionRecord

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
3. Evaluate each movie independently against the criteria — never relative to the other movies in the list. The list you receive is an arbitrary slice of the library, and the same movie must get the same verdict regardless of which other movies happen to appear alongside it.
4. For each movie, reason briefly about the fit FIRST (the reasoning field), then commit to include and confidence. Keep reasoning to a sentence or two; it matters most for borderline cases.
5. Provide a confidence score (0.0-1.0) for each decision: your confidence in the include/exclude call you made
6. Do not consider personal preferences or subjective quality judgments

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
- The "keywords" field contains community-sourced tags: useful signals for themes and subject matter, but not verdicts — a movie tagged "heist" is not necessarily a heist movie

IMPORTANT: For collections based on themes or genres, focus on whether the movie is primarily about that theme/genre, not whether it contains elements of it. For example:
- A movie with one heist scene is not necessarily a "Heist Movie"
- A movie set partly in space is not necessarily a "Space Movie"
- A movie with some comedy is not necessarily a "Comedy Movie"

PREVIOUS DECISIONS: Some movies carry a "previous_decision" field from an earlier evaluation of this same collection. Treat it as the standing verdict: keep it unless you have a clear, articulable reason the movie was misclassified. Do not flip a previous decision based on a marginally different reading of the same evidence — consistency across runs matters more than second-guessing borderline calls. If you do flip one, state the reason in the reasoning field.
"""


def format_collection_prompt(collection: CollectionConfig) -> str:
    """Format the prompt for a collection.

    Args:
        collection: Collection configuration

    Returns:
        Formatted prompt
    """
    formatted_prompt = collection.prompt.strip() if collection.prompt else ""

    if not formatted_prompt:
        logger.warning(f"Collection '{collection.name}' has an empty prompt!")

    return f"""
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
"""


def format_movies_data(
    movies: List[Movie],
    prior_decisions: Optional[Dict[int, DecisionRecord]] = None
) -> str:
    """Format movie data for Claude prompt.

    Args:
        movies: List of movies
        prior_decisions: Previous decisions for this collection keyed by movie
            ID; included so Claude can anchor re-evaluations to the standing
            verdict

    Returns:
        Formatted movie data as JSON
    """
    movies_data = []
    for movie in movies:
        movie_data = {
            "movie_id": movie.id,
            "title": movie.title,
            "year": movie.year,
            "genres": movie.genres,
            "overview": movie.overview,
        }

        if movie.keywords:
            movie_data["keywords"] = movie.keywords
        if movie.certification:
            movie_data["certification"] = movie.certification
        if movie.original_language:
            movie_data["original_language"] = movie.original_language
        if movie.imdb_rating:
            movie_data["imdb_rating"] = movie.imdb_rating
        if movie.rotten_tomatoes:
            movie_data["rotten_tomatoes_pct"] = movie.rotten_tomatoes
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

        prior = (prior_decisions or {}).get(movie.id)
        if prior is not None:
            movie_data["previous_decision"] = {
                "include": prior.include,
                "confidence": prior.confidence,
            }

        movies_data.append(movie_data)

    return json.dumps(movies_data, indent=2)
