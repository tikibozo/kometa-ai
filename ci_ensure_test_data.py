#!/usr/bin/env python3
"""
Create test data for CI testing.
"""

import json
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ci_ensure_test_data")

def create_test_data():
    """Create the test data files needed for testing."""
    test_dir = Path.cwd() / "test_data"
    
    # Create directory if it doesn't exist
    if not test_dir.exists():
        test_dir.mkdir(parents=True)
        logger.info(f"Created test_data directory at {test_dir}")
    
    # Create __init__.py
    init_file = test_dir / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write('"""Test data for Kometa-AI."""\n')
        logger.info(f"Created {init_file}")
    
    # Sample movie data
    synthetic_movies = [
        {
            "id": 1001,
            "title": "The Adventure Quest",
            "year": 2020,
            "overview": "A group of friends embark on an epic adventure to find a hidden treasure.",
            "genres": ["Adventure", "Action", "Fantasy"],
            "tagline": "The greatest adventure awaits",
            "runtime": 124,
            "rating": 7.8,
            "director": "Jane Smith",
            "actors": ["John Doe", "Sarah Johnson", "Mike Williams"],
            "studio": "Adventure Studios"
        },
        {
            "id": 1002,
            "title": "Mystery in the Dark",
            "year": 2018,
            "overview": "A detective investigates a series of mysterious disappearances in a small town.",
            "genres": ["Mystery", "Thriller", "Crime"],
            "tagline": "The truth lies in the shadows",
            "runtime": 112,
            "rating": 8.2,
            "director": "Robert Brown",
            "actors": ["Emily Clark", "David Wilson", "Linda Martin"],
            "studio": "Enigma Pictures"
        },
        {
            "id": 1003,
            "title": "Laugh Out Loud",
            "year": 2021,
            "overview": "A stand-up comedian tries to make it big while dealing with personal challenges.",
            "genres": ["Comedy", "Drama"],
            "tagline": "Sometimes life is the best punchline",
            "runtime": 98,
            "rating": 7.5,
            "director": "Michael Johnson",
            "actors": ["Lisa Adams", "Tom Clark", "Kevin White"],
            "studio": "Funny Films"
        }
    ]
    
    # Sample collection data
    synthetic_collections = [
        {
            "name": "Adventure Films",
            "description": "Movies focused on exciting journeys, quests, and exploration.",
            "criteria": "Movies with adventure themes, often featuring quests, journeys, or exploration into unknown territories.",
            "tag": "adventure-films",
            "enabled": True
        },
        {
            "name": "Mystery Thrillers",
            "description": "Suspenseful movies with mystery elements.",
            "criteria": "Films that combine mystery and thriller elements, featuring investigations, suspense, and plot twists.",
            "tag": "mystery-thrillers",
            "enabled": True
        },
        {
            "name": "Comedy Collection",
            "description": "Funny movies to lighten the mood.",
            "criteria": "Movies intended to make the audience laugh through humor, amusing situations, and comedy.",
            "tag": "comedy-collection",
            "enabled": True
        }
    ]
    
    # Write JSON files
    movies_file = test_dir / "synthetic_movies.json"
    collections_file = test_dir / "synthetic_collections.json"
    
    with open(movies_file, "w") as f:
        json.dump(synthetic_movies, f, indent=2)
    logger.info(f"Created {movies_file}")
    
    with open(collections_file, "w") as f:
        json.dump(synthetic_collections, f, indent=2)
    logger.info(f"Created {collections_file}")
    
    # Create Python module
    module_file = test_dir / "synthetic_movies.py"
    with open(module_file, "w") as f:
        f.write("""
\"\"\"
Synthetic test data for movies and collections.
This module provides sample data for testing without requiring external APIs.
\"\"\"

from typing import Dict, List, Any

# Sample synthetic movies with metadata
synthetic_movies = {movies}

# Sample collection definitions
synthetic_collections = {collections}
""".format(
            movies=json.dumps(synthetic_movies, indent=4),
            collections=json.dumps(synthetic_collections, indent=4)
        ))
    logger.info(f"Created {module_file}")
    
    logger.info("Test data creation completed")
    
    # List all files
    logger.info("Files created:")
    for file in test_dir.glob("*"):
        logger.info(f"  {file}")

if __name__ == "__main__":
    create_test_data()