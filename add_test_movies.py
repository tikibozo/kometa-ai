#!/usr/bin/env python3
"""
Script to add sample movies to Radarr for testing purposes.
This is useful for quickly setting up a test environment.
"""

import sys
import time
import subprocess
import json

try:
    import requests
except ImportError:
    print("\n============ Package Dependency Missing ============")
    print("The 'requests' package is required but not installed.")
    print("Since you're in a managed environment, please run:")
    print("pip install --user requests")
    print("or")
    print("brew install python-requests")
    print("=================================================\n")
    sys.exit(1)

# Configuration
API_URL = "http://localhost:7878/api/v3"
API_KEY = "0123456789abcdef0123456789abcdef"

# Sample movies representing different genres for testing
SAMPLE_MOVIES = [
    # Action movies
    {"tmdbId": 27205, "title": "Inception"},
    {"tmdbId": 155, "title": "The Dark Knight"},
    
    # Comedy movies
    {"tmdbId": 4922, "title": "The Hangover"},
    {"tmdbId": 109439, "title": "The Grand Budapest Hotel"},
    
    # Drama movies
    {"tmdbId": 13, "title": "Forrest Gump"},
    {"tmdbId": 550, "title": "Fight Club"},
    
    # Sci-Fi movies
    {"tmdbId": 603, "title": "The Matrix"},
    {"tmdbId": 335984, "title": "Blade Runner 2049"},
    
    # Thriller movies
    {"tmdbId": 680, "title": "Pulp Fiction"},
    {"tmdbId": 807, "title": "Se7en"}
]

def make_api_request(method, endpoint, data=None):
    """Make a request to the Radarr API."""
    url = f"{API_URL}/{endpoint}"
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            print(f"Unsupported HTTP method: {method}")
            return None
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

def check_radarr_connection():
    """Check if Radarr is available and the API key is correct."""
    print("Checking connection to Radarr...")
    try:
        response = make_api_request("GET", "system/status")
        if response:
            print(f"Connected to Radarr version {response.get('version', 'unknown')}")
            return True
        else:
            print("Failed to connect to Radarr. Check if it's running and the API key is correct.")
            return False
    except Exception as e:
        print(f"Error checking Radarr connection: {e}")
        return False

def lookup_movie(tmdb_id):
    """Look up a movie by TMDb ID."""
    return make_api_request("GET", f"movie/lookup/tmdb?tmdbId={tmdb_id}")

def add_movie(movie_data):
    """Add a movie to Radarr."""
    # Set default quality profile and path
    movie_data["qualityProfileId"] = 1  # Default profile ID
    movie_data["rootFolderPath"] = "/movies"  # Default movie path
    movie_data["monitored"] = True
    movie_data["addOptions"] = {"searchForMovie": False}  # Don't search for the movie
    
    return make_api_request("POST", "movie", movie_data)

def main():
    """Main function to add sample movies to Radarr."""
    if not check_radarr_connection():
        sys.exit(1)
    
    print("\nAdding sample movies to Radarr...")
    added_count = 0
    
    for sample in SAMPLE_MOVIES:
        print(f"\nLooking up {sample['title']} (TMDb ID: {sample['tmdbId']})...")
        movie_data = lookup_movie(sample['tmdbId'])
        
        if not movie_data:
            print(f"Failed to lookup {sample['title']}, skipping.")
            continue
        
        print(f"Adding {movie_data['title']} ({movie_data.get('year', 'N/A')})...")
        result = add_movie(movie_data)
        
        if result:
            print(f"Successfully added {result['title']} (ID: {result['id']})")
            added_count += 1
        else:
            print(f"Failed to add {sample['title']}")
        
        # Slight delay to avoid API rate limiting
        time.sleep(1)
    
    print(f"\nCompleted! Added {added_count} out of {len(SAMPLE_MOVIES)} sample movies.")

if __name__ == "__main__":
    main()