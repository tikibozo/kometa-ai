#!/bin/bash

# Master script for testing against Radarr
# This script replaces the multiple scripts created during development

set -e  # Exit on any error

# Configuration
API_KEY="0123456789abcdef0123456789abcdef"
RADARR_URL="http://localhost:7878"
API_URL="${RADARR_URL}/api/v3"

# Color codes for better output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print colored status messages
status() {
  echo -e "${GREEN}==>${NC} $1"
}

warning() {
  echo -e "${YELLOW}==>${NC} $1"
}

error() {
  echo -e "${RED}==>${NC} $1"
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

# Function to check if Radarr is responding
check_radarr() {
  status "Checking if Radarr is responding..."
  if curl -s -f -m 5 ${RADARR_URL} > /dev/null; then
    success "Radarr is responding"
    return 0
  else
    warning "Radarr is not responding yet. Waiting..."
    return 1
  fi
}

# Function to check API key
check_api_key() {
  status "Checking API key..."
  API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${API_URL}/system/status -H "X-Api-Key: ${API_KEY}")
  
  if [ "$API_STATUS" = "200" ]; then
    success "API key is working"
    return 0
  else
    warning "API key is not working (HTTP status: $API_STATUS)"
    return 1
  fi
}

# Function to set up Radarr root folder
setup_radarr() {
  status "Setting up Radarr root folder..."
  ROOT_FOLDER_JSON='{
    "path": "/movies",
    "name": "Movies",
    "defaultTags": [],
    "defaultQualityProfileId": 1,
    "defaultMonitored": true
  }'

  ROOT_FOLDER_RESPONSE=$(curl -s -X POST "${API_URL}/rootfolder" \
    -H "X-Api-Key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$ROOT_FOLDER_JSON")

  # Check if root folder was added successfully
  if [[ "$ROOT_FOLDER_RESPONSE" == *"id"* ]]; then
    success "Successfully added /movies root folder"
  elif [[ "$ROOT_FOLDER_RESPONSE" == *"Path already configured"* ]]; then
    success "Root folder /movies already exists"
  else
    error "Failed to add root folder: $ROOT_FOLDER_RESPONSE"
    return 1
  fi
  
  return 0
}

# Function to add sample movies
add_sample_movies() {
  status "Adding sample movies to Radarr..."
  
  # Sample movies with hardcoded details
  MOVIE_IDS=(
    "27205" "155" "4922" "109439" "13" "550" "603" "335984" "680" "807"
  )
  MOVIE_TITLES=(
    "Inception" "The Dark Knight" "The Hangover" "The Grand Budapest Hotel" 
    "Forrest Gump" "Fight Club" "The Matrix" "Blade Runner 2049" 
    "Pulp Fiction" "Se7en"
  )
  
  ADDED_COUNT=0
  
  # Loop through movie arrays
  for i in "${!MOVIE_IDS[@]}"; do
    TMDB_ID="${MOVIE_IDS[$i]}"
    TITLE="${MOVIE_TITLES[$i]}"
    status "Adding movie: ${TITLE} (TMDB ID: ${TMDB_ID})..."
    
    # Create a simple JSON file for this movie
    cat > movie_${TMDB_ID}.json << EOF
{
  "tmdbId": ${TMDB_ID},
  "title": "${TITLE}",
  "qualityProfileId": 1,
  "rootFolderPath": "/movies",
  "monitored": true,
  "addOptions": {
    "searchForMovie": false
  }
}
EOF
  
    # Add the movie using the JSON file
    ADD_RESPONSE=$(curl -s -X POST "${API_URL}/movie" \
      -H "X-Api-Key: ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d @movie_${TMDB_ID}.json)
    
    # Check if add was successful or already exists
    if [[ "$ADD_RESPONSE" == *"\"id\""* ]]; then
      MOVIE_ID=$(echo "$ADD_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | sed 's/"id"://')
      success "Added \"${TITLE}\" (ID: ${MOVIE_ID})"
      ADDED_COUNT=$((ADDED_COUNT + 1))
    elif [[ "$ADD_RESPONSE" == *"This movie has already been added"* ]]; then
      success "\"${TITLE}\" already exists in Radarr"
      ADDED_COUNT=$((ADDED_COUNT + 1))
    else
      warning "Failed to add \"${TITLE}\""
    fi
    
    # Clean up
    rm -f movie_${TMDB_ID}.json
    
    sleep 1  # Slight delay to avoid overwhelming the API
  done
  
  success "Added/verified ${ADDED_COUNT} out of ${#MOVIE_IDS[@]} sample movies"
}

# Function to run the tests
run_tests() {
  status "Running tests against Radarr..."
  
  # Always use Docker for consistent environment
  status "Running tests in Docker container..."
  
  # Start radarr container if not running
  if ! docker ps | grep -q kometa-ai-radarr; then
    warning "Radarr container not running, starting it now..."
    docker-compose -f docker-compose.test.yml up -d radarr
    sleep 5
  fi
  
  # Run tests in Docker container
  docker-compose -f docker-compose.test.yml run --rm --entrypoint bash kometa-ai -c "RADARR_URL=${RADARR_URL} RADARR_API_KEY=${API_KEY} python -m pytest tests/test_radarr_tag_manager.py -v"
  TEST_RESULT=$?
  
  if [ $TEST_RESULT -eq 0 ]; then
    success "Tests completed successfully"
    return 0
  else
    error "Tests failed"
    return 1
  fi
}

# Main function - handle different commands
main() {
  command=$1
  
  case $command in
    start)
      status "Starting Radarr test environment..."
      docker-compose -f docker-compose.test.yml down
      docker-compose -f docker-compose.test.yml up -d radarr
      
      # Wait for Radarr to start
      for i in {1..30}; do
        if check_radarr; then
          break
        fi
        if [ $i -eq 30 ]; then
          error "Radarr failed to start after 30 attempts"
          exit 1
        fi
        sleep 5
      done
      
      success "Radarr test environment started"
      ;;
      
    setup)
      check_api_key
      if [ $? -ne 0 ]; then
        error "API key is not working. Make sure Radarr is running and set up the API key first."
        exit 1
      fi
      
      setup_radarr
      add_sample_movies
      ;;
      
    test)
      check_api_key
      if [ $? -ne 0 ]; then
        error "API key is not working. Make sure Radarr is running and set up first."
        exit 1
      fi
      
      run_tests
      ;;
      
    validate)
      status "Starting full validation process..."
      
      # Step 1: Start environment
      main start
      
      # Step 2: Set up Radarr
      status "Setting up Radarr..."
      check_api_key
      if [ $? -ne 0 ]; then
        warning "API key is not working. Please set up Radarr manually."
        echo "1. Open ${RADARR_URL} in your browser"
        echo "2. Complete the setup wizard"
        echo "3. Set the API Key to ${API_KEY} in Settings > General"
        echo ""
        read -p "Press Enter once you've completed the Radarr setup..." </dev/tty
      fi
      
      # Step 3: Setup and add sample movies
      main setup
      
      # Step 4: Run tests
      main test
      
      # Step 5: Run app
      status "Starting Kometa-AI app against Radarr..."
      docker-compose -f docker-compose.test.yml up -d kometa-ai
      
      success "Validation complete"
      echo ""
      echo "You can check the app logs with:"
      echo "docker-compose -f docker-compose.test.yml logs -f kometa-ai"
      echo ""
      echo "To shut down the environment run:"
      echo "./radarr_test.sh stop"
      ;;
      
    stop)
      status "Stopping Radarr test environment..."
      docker-compose -f docker-compose.test.yml down
      success "Environment stopped"
      ;;
      
    *)
      echo "Radarr Test Environment"
      echo "Usage: ./radarr_test.sh [command]"
      echo ""
      echo "Commands:"
      echo "  start     - Start the Radarr test environment"
      echo "  setup     - Set up Radarr with root folder and sample movies"
      echo "  test      - Run tests against Radarr"
      echo "  validate  - Run the full validation process"
      echo "  stop      - Stop the Radarr test environment"
      ;;
  esac
}

# Run the main function with the provided command
main "$1"
