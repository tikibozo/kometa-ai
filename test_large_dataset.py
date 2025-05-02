#!/usr/bin/env python3
"""
Script to test Kometa-AI with large movie datasets.
This allows testing memory usage, performance, and batch processing capabilities.
"""

import os
import sys
import json
import time
import argparse
import logging
import tracemalloc
from datetime import datetime

from kometa_ai.config import Config
from kometa_ai.utils.logging import setup_logging
from kometa_ai.radarr.models import Movie
from kometa_ai.claude.client import ClaudeClient
from kometa_ai.claude.processor import MovieProcessor
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.state.manager import StateManager
from kometa_ai.utils.profiling import profiler

# Configure logging
setup_logging(debug=True)
logger = logging.getLogger(__name__)

def load_movies_from_file(file_path):
    """Load generated movies from a JSON file."""
    logger.info(f"Loading movies from {file_path}")
    with open(file_path, "r") as f:
        movie_data = json.load(f)
    
    # Convert to Movie objects
    movies = [Movie.from_dict(m) for m in movie_data]
    logger.info(f"Loaded {len(movies)} movies from dataset")
    return movies

def create_test_collection():
    """Create a test collection for classification."""
    collection = CollectionConfig(
        name="Performance Test Collection",
        enabled=True,
        tag="KAI-perf-test",
        prompt="""
        This collection includes action movies with high-stakes plots, exciting sequences, and clear protagonists and antagonists.
        
        Consider these criteria:
        - Films with extensive action sequences (car chases, fights, explosions, etc.)
        - High-stakes scenarios where the protagonist must save someone/something
        - Typically features a clear hero and villain
        - Often contains stunts and special effects
        - Pacing is usually fast with minimal slow or contemplative scenes
        - Focus on physical conflict rather than psychological or emotional conflict
        
        Common sub-genres include spy action, martial arts, military action, disaster films, and superhero movies.
        """,
        confidence_threshold=0.7
    )
    return collection

def run_performance_test(movies, batch_size, state_dir):
    """Run a performance test with the given parameters."""
    logger.info(f"Starting performance test with {len(movies)} movies and batch_size={batch_size}")
    
    # Start memory tracking
    tracemalloc.start()
    
    # Start profiling
    profiler.start()
    
    # Create a mock Claude client for testing
    class MockClaudeClient:
        def __init__(self):
            self.usage_stats = {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost': 0.0,
                'requests': 0,
                'start_time': datetime.now().isoformat()
            }
        
        def classify_movies(self, system_prompt, collection_prompt, movies_data, batch_size):
            # Simulate API call with mock data
            # We'll return a simple response that includes 20% of movies
            movie_ids = [int(line.split(':')[1].strip().split(',')[0]) 
                        for line in movies_data.split('\n') 
                        if line.startswith('- ID:')]
            
            decisions = []
            for movie_id in movie_ids:
                # Include 20% of movies randomly
                include = movie_id % 5 == 0
                decisions.append({
                    'movie_id': movie_id,
                    'title': f"Movie {movie_id}",
                    'include': include,
                    'confidence': 0.8 if include else 0.2
                })
            
            # Simulate token usage
            tokens_per_movie = 100
            self.usage_stats['total_input_tokens'] += len(movie_ids) * tokens_per_movie
            self.usage_stats['total_output_tokens'] += len(decisions) * 50
            self.usage_stats['total_cost'] += (self.usage_stats['total_input_tokens'] / 1_000_000 * 3.0) + (self.usage_stats['total_output_tokens'] / 1_000_000 * 15.0)
            self.usage_stats['requests'] += 1
            
            return {
                'collection_name': 'Test Collection',
                'decisions': decisions
            }, self.usage_stats
        
        def get_usage_stats(self):
            return self.usage_stats
        
        def reset_usage_stats(self):
            self.usage_stats = {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_cost': 0.0,
                'requests': 0,
                'start_time': datetime.now().isoformat()
            }
    
    # Use mock client instead of real API
    claude_client = MockClaudeClient()
    
    # Create state manager
    state_manager = StateManager(state_dir)
    state_manager.load()
    
    # Create test collection
    collection = create_test_collection()
    
    # Create movie processor with the specified batch size
    processor = MovieProcessor(
        claude_client=claude_client,
        state_manager=state_manager,
        batch_size=batch_size,
        force_refresh=True
    )
    
    # Process collection
    start_time = time.time()
    included_ids, excluded_ids, stats = processor.process_collection(
        collection=collection,
        movies=movies
    )
    duration = time.time() - start_time
    
    # Get profiling results
    profiling_results = profiler.stop()
    
    # Get memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Log results
    logger.info(f"Performance test completed in {duration:.2f} seconds")
    logger.info(f"Included movies: {len(included_ids)}, Excluded movies: {len(excluded_ids)}")
    logger.info(f"Memory usage - Current: {current / 1024 / 1024:.2f} MB, Peak: {peak / 1024 / 1024:.2f} MB")
    
    # Save results
    results = {
        "timestamp": datetime.now().isoformat(),
        "movie_count": len(movies),
        "batch_size": batch_size,
        "duration": duration,
        "included_count": len(included_ids),
        "excluded_count": len(excluded_ids),
        "memory": {
            "current": current,
            "peak": peak
        },
        "stats": stats,
        "profiling": profiling_results
    }
    
    results_file = os.path.join(state_dir, f"performance_test_{len(movies)}_{batch_size}.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Results saved to {results_file}")
    
    return results

def parse_args():
    parser = argparse.ArgumentParser(description="Test Kometa-AI with large movie datasets")
    parser.add_argument("-f", "--file", type=str, required=True,
                        help="Path to the movie dataset JSON file")
    parser.add_argument("-b", "--batch-size", type=int, default=150,
                        help="Batch size for processing (default: 150)")
    parser.add_argument("-s", "--state-dir", type=str, default="./test_state",
                        help="Directory for state storage (default: ./test_state)")
    parser.add_argument("-l", "--limit", type=int, default=None,
                        help="Limit the number of movies to process (default: all)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Create state directory if it doesn't exist
    os.makedirs(args.state_dir, exist_ok=True)
    
    # Load movies
    movies = load_movies_from_file(args.file)
    
    # Apply limit if specified
    if args.limit and args.limit < len(movies):
        logger.info(f"Limiting dataset to {args.limit} movies")
        movies = movies[:args.limit]
    
    # Run performance test
    run_performance_test(movies, args.batch_size, args.state_dir)

if __name__ == "__main__":
    main()