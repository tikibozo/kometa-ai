"""
Memory optimization utilities for Kometa-AI.

This module provides tools for optimizing memory usage in the application,
particularly for large movie libraries.
"""

import logging
import gc
import sys
from typing import List, Any, Dict, Callable, TypeVar, cast

logger = logging.getLogger(__name__)

# Type variable for chunking operations
T = TypeVar('T')


def clear_memory():
    """Force garbage collection to clear memory."""
    logger.debug("Running full garbage collection to clear memory")
    gc.collect(generation=2)


def get_size(obj: Any, seen: set = None) -> int:
    """Recursively calculate the size of an object in bytes.

    Args:
        obj: Object to measure
        seen: Set of already seen object ids (for recursion)

    Returns:
        Size in bytes
    """
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0

    seen.add(obj_id)
    size = sys.getsizeof(obj)

    if isinstance(obj, dict):
        for k, v in obj.items():
            size += get_size(k, seen) + get_size(v, seen)
    elif isinstance(obj, (list, tuple, set)):
        for item in obj:
            size += get_size(item, seen)

    return size


def optimize_movie_objects(movies: List[Any]) -> List[Any]:
    """Optimize memory usage of movie objects.

    Reduces memory usage by removing unnecessary attributes and data
    that's not needed for classification.

    Args:
        movies: List of Movie objects or dictionaries

    Returns:
        List of optimized Movie objects or dictionaries
    """
    logger.debug(f"Optimizing {len(movies)} movie objects for memory efficiency")

    # Fields needed for Claude classification
    essential_fields = {
        'id', 'title', 'year', 'overview', 'genres', 'tags',
        'runtime', 'ratings', 'tmdbId', 'imdbId'
    }

    # Fields needed for metadata hash calculation
    hash_fields = {
        'title', 'year', 'overview', 'genres', 'tags'
    }

    # Make a shallow copy of each movie, keeping only essential data
    optimized_movies = []

    for movie in movies:
        # Handle both object and dictionary formats
        if isinstance(movie, dict):
            # For dictionaries, create a new dict with only essential fields
            optimized_movie = {}
            for field in essential_fields:
                if field in movie:
                    optimized_movie[field] = movie[field]

            # Always include these fields if available
            for field in ['id', 'title', 'year']:
                if field in movie:
                    optimized_movie[field] = movie[field]

        else:
            # For objects, create a new object with only essential attributes
            try:
                # Try to create a new instance of the same type
                optimized_movie = type(movie)(
                    id=movie.id,
                    title=movie.title,
                    year=movie.year
                )

                # Copy only the essential fields
                for field in essential_fields:
                    if hasattr(movie, field) and field not in ('id', 'title', 'year'):
                        value = getattr(movie, field)
                        setattr(optimized_movie, field, value)

                # Ensure the metadata hash calculation still works
                if hasattr(movie, 'calculate_metadata_hash'):
                    optimized_movie.calculate_metadata_hash = movie.calculate_metadata_hash
            except (AttributeError, TypeError):
                # If we can't create a new instance, just use the original
                optimized_movie = movie

        optimized_movies.append(optimized_movie)

    # Force garbage collection to free memory
    clear_memory()

    logger.debug(f"Movie objects optimized for memory efficiency")
    return optimized_movies


def process_in_chunks(items: List[T], chunk_size: int, processor: Callable[[List[T]], Any]) -> List[Any]:
    """Process a large list of items in smaller chunks to reduce memory usage.

    Args:
        items: List of items to process
        chunk_size: Size of each chunk
        processor: Function to call with each chunk

    Returns:
        Combined results from processing each chunk
    """
    logger.debug(f"Processing {len(items)} items in chunks of {chunk_size}")

    results = []

    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        logger.debug(f"Processing chunk {i//chunk_size + 1}/{(len(items) + chunk_size - 1)//chunk_size} with {len(chunk)} items")

        # Process this chunk
        chunk_result = processor(chunk)
        results.append(chunk_result)

        # Force garbage collection between chunks
        clear_memory()

    return results


def optimize_state_memory(state: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize memory usage of the state dictionary.

    Reduces memory usage by optimizing how decisions are stored.

    Args:
        state: State dictionary

    Returns:
        Optimized state dictionary
    """
    logger.debug("Optimizing state dictionary for memory efficiency")

    # No deep changes to the state format yet, but this function provides
    # a hook for future optimizations

    # For now, just return the original state
    return state


def memory_efficient_format(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert data to a more memory-efficient format for storage.

    Args:
        data: Data dictionary

    Returns:
        Memory-optimized data dictionary
    """
    # Basic implementation - can be expanded in the future
    return data
