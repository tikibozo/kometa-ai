#!/usr/bin/env python3
"""
Script to generate large synthetic movie datasets for performance testing.
This is useful for testing memory usage and batch processing with large libraries.
"""

import os
import sys
import json
import random
import argparse
from datetime import datetime, timedelta
import uuid

# Sample genre pool
GENRES = [
    "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
    "Drama", "Family", "Fantasy", "Film-Noir", "History", "Horror",
    "Music", "Musical", "Mystery", "Romance", "Sci-Fi", "Short",
    "Sport", "Thriller", "War", "Western"
]

# Sample synopsis templates
SYNOPSIS_TEMPLATES = [
    "A {adj1} {character} must {action} the {adj2} {villain} before {consequence}.",
    "In a {adj1} world where {situation}, a {character} discovers {discovery} that will change everything.",
    "After {event}, a {character} decides to {action} with the help of {helper}.",
    "When {character} {action}, they discover {discovery} that leads them on a journey to {goal}.",
    "{character} must {action} to save {something} from {villain} before {consequence}."
]

# Sample elements for synopsis generation
SYNOPSIS_ELEMENTS = {
    "adj1": ["dystopian", "futuristic", "medieval", "post-apocalyptic", "magical", "cyberpunk", "war-torn", "peaceful"],
    "adj2": ["evil", "corrupt", "ruthless", "powerful", "mysterious", "ancient", "technological", "supernatural"],
    "character": ["detective", "soldier", "scientist", "teacher", "hacker", "wizard", "pilot", "doctor", "spy", "thief"],
    "villain": ["organization", "government", "corporation", "warlord", "AI", "alien race", "crime syndicate", "cult"],
    "action": ["defeat", "outsmart", "escape from", "infiltrate", "negotiate with", "survive", "expose", "destroy"],
    "consequence": ["time runs out", "all hope is lost", "the world is destroyed", "humanity is enslaved"],
    "situation": ["resources are scarce", "privacy no longer exists", "magic has returned", "technology controls everything"],
    "discovery": ["a conspiracy", "a hidden power", "a dark secret", "a new technology", "an ancient artifact"],
    "event": ["losing everything", "witnessing a crime", "surviving a disaster", "receiving mysterious powers"],
    "helper": ["an unlikely ally", "a former enemy", "cutting-edge technology", "an old friend", "a mysterious stranger"],
    "goal": ["redemption", "revenge", "save humanity", "find the truth", "return home", "restore balance"],
    "something": ["their family", "their city", "humanity", "the world", "the future", "ancient knowledge"]
}

def generate_synopsis():
    """Generate a random movie synopsis."""
    template = random.choice(SYNOPSIS_TEMPLATES)
    
    for key, options in SYNOPSIS_ELEMENTS.items():
        if "{" + key + "}" in template:
            template = template.replace("{" + key + "}", random.choice(options))
    
    # Add some additional sentences for longer synopses
    extra_sentences = [
        "The stakes have never been higher.",
        "Time is running out.",
        "Nothing is as it seems.",
        "Allies become enemies and enemies become allies.",
        "The truth lies beneath the surface.",
        "The journey will test their limits.",
        "The past and future collide.",
        "Unexpected twists change everything."
    ]
    
    # Add 1-3 extra sentences
    num_extras = random.randint(1, 3)
    template += " " + " ".join(random.sample(extra_sentences, num_extras))
    
    return template

def generate_movie(movie_id):
    """Generate a synthetic movie with the given ID."""
    current_year = datetime.now().year
    year = random.randint(current_year - 70, current_year)
    
    # Generate a somewhat realistic title
    title_elements = {
        "adjectives": ["Dark", "Lost", "Eternal", "Final", "First", "Silent", "Hidden", "Rising", "Fallen", "Last"],
        "nouns": ["Kingdom", "Legacy", "Night", "Dawn", "Light", "Shadow", "Dream", "Memory", "Journey", "Paradise", "Justice"],
        "connectors": ["of", "in", "beyond", "against", "within", "without", "through", "under", "above"]
    }
    
    # 20% chance for a "The" prefix
    prefix = "The " if random.random() < 0.2 else ""
    
    # Different title patterns
    pattern = random.randint(1, 5)
    if pattern == 1:
        # "The Dark Knight"
        title = f"{prefix}{random.choice(title_elements['adjectives'])} {random.choice(title_elements['nouns'])}"
    elif pattern == 2:
        # "Inception"
        title = random.choice([
            "Inception", "Interstellar", "Avatar", "Titanic", "Joker", "Parasite", "Nomadland", "Arrival",
            "Twilight", "Moonlight", "Skyfall", "Gravity", "Whiplash", "Blade", "Dune", "Matrix", "Jaws"
        ]) + str(random.randint(1, 3)) if random.random() < 0.3 else ""
    elif pattern == 3:
        # "The Lord of the Rings"
        title = f"{prefix}{random.choice(title_elements['nouns'])} {random.choice(title_elements['connectors'])} the {random.choice(title_elements['nouns'])}"
    elif pattern == 4:
        # "Star Wars: A New Hope"
        franchise = random.choice(["Star", "Planet", "Ocean", "Mountain", "Galaxy", "Time", "Space"])
        subtitle = f"{random.choice(['A', 'The'])} {random.choice(title_elements['adjectives'])} {random.choice(title_elements['nouns'])}"
        title = f"{franchise} {random.choice(['Wars', 'Trek', 'Quest', 'Chronicles', 'Legacy'])}: {subtitle}"
    else:
        # Simple two-word title
        title = f"{random.choice(title_elements['adjectives'])} {random.choice(title_elements['nouns'])}"
    
    # Sometimes add a year range for sequels
    if random.random() < 0.1 and pattern != 4:  # Skip for franchise titles
        title = f"{title} ({year}-{year+random.randint(5, 10)})"
    
    num_genres = random.randint(1, 3)
    movie_genres = random.sample(GENRES, num_genres)
    
    # Runtime between 80 and 180 minutes
    runtime = random.randint(80, 180)
    
    # Generate random TMDB and IMDB IDs
    tmdb_id = movie_id + 1000  # Just to have different IDs
    imdb_id = f"tt{random.randint(1000000, 9999999)}"
    
    # Generate random user rating between 1.0 and 10.0
    rating = round(random.uniform(4.0, 9.5), 1)
    
    return {
        "id": movie_id,
        "title": title,
        "sortTitle": title.replace("The ", ""),
        "year": year,
        "overview": generate_synopsis(),
        "runtime": runtime,
        "genres": movie_genres,
        "ratings": {
            "imdb": {
                "value": rating,
                "votes": random.randint(1000, 500000)
            }
        },
        "imdbId": imdb_id,
        "tmdbId": tmdb_id,
        "physicalRelease": f"{year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "added": (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat()
    }

def generate_dataset(num_movies, output_file):
    """Generate a synthetic movie dataset with the specified number of movies."""
    movies = []
    
    for i in range(num_movies):
        if i % 100 == 0:
            print(f"Generating movie {i+1}/{num_movies}...")
        movies.append(generate_movie(i + 1))
    
    # Save to file
    with open(output_file, "w") as f:
        json.dump(movies, f, indent=2)
    
    print(f"Successfully generated dataset with {num_movies} movies: {output_file}")

def parse_args():
    parser = argparse.ArgumentParser(description="Generate synthetic movie datasets for testing")
    parser.add_argument("-n", "--num-movies", type=int, default=1000,
                        help="Number of movies to generate (default: 1000)")
    parser.add_argument("-o", "--output", type=str, default="test_data/movies.json",
                        help="Output file path (default: test_data/movies.json)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Generate the dataset
    generate_dataset(args.num_movies, args.output)

if __name__ == "__main__":
    main()