# Kometa-AI Radarr Integration

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Execution Flow](#execution-flow)
4. [Configuration](#configuration)
   - [Environment Variables](#environment-variables)
   - [Docker Volume](#docker-volume)
5. [Scheduling](#scheduling)
6. [Tagging Convention](#tagging-convention)
7. [Collection Configuration](#collection-configuration)
8. [Notification System](#notification-system)
9. [Error Handling](#error-handling)
   - [Specific Error Handling Strategies](#specific-error-handling-strategies)
10. [Security Considerations](#security-considerations)
11. [Implementation & Deployment](#implementation--deployment)
    - [Docker-First Approach](#docker-first-approach)
    - [CLI Interface](#cli-interface)
    - [Version Management](#version-management)
    - [Code Quality & Testing](#code-quality--testing-standards)
    - [Monitoring & Resilience](#monitoring--resilience)
12. [Technical Design](#technical-design)
    - [Code Organization](#code-organization)
    - [Development Stages](#development-stages)
    - [Testing Strategy](#testing-strategy)
    - [Incremental Deployment](#incremental-deployment)
13. [Detailed Implementation Specifications](#detailed-implementation-specifications)
    - [Claude API Integration](#claude-api-integration)
    - [State Management](#state-management)
    - [Tag Reconciliation Logic](#tag-reconciliation-logic)
    - [Collection Parsing](#collection-parsing)
14. [Future Extensions](#future-extensions)

## Overview
Kometa-AI integrates Claude into Kometa to select movies to include in a given collection. This enables you to create collections based on LLM prompts rather than just metadata tags, manual lists or the other standard Kometa collection types. 

Kometa-AI is a dockerized python script that queries Radarr for movies, metadata, and tags, examines AI-tagged collections in Kometa, evaluates the movies using a provdided prompt, and then updates tags in Radarr accordingly. Kometa can then consume this output of this as a standard Radarr tag collection. This approach creates a bridge between Radarr's tagging system and Kometa's collection management, ultimately affecting how movies are organized in Plex.

## Architecture
- **Implementation**: Dockerized Python script
- **Execution**: Self-contained with internal scheduling
- **Configuration**: Environment variables and mounted Kometa config

## Execution Flow
1. **Data Collection**
   - Read movies and tags from Radarr API
   - Read collections and prompts from Kometa configuration
   - Filter collections to those configured for this script

2. **AI Processing**
   - Initialize Claude session, providing movie list and metadata
   - For each configured collection:
     - Submit collection details to Claude
     - Process AI response to determine tag changes

3. **Tag Management**
   - Add/remove tags from movies in Radarr based on AI decisions
   - Track changes for reporting

4. **Reporting**
   - Send email summary of changes
   - Include collection-by-collection breakdown
   - Report any errors or issues encountered

5. **Integration Point**
   - When Kometa runs, it will update Plex collections based on the Radarr tags

## Configuration

### Environment Variables
- `RADARR_URL`: Base URL for Radarr instance
- `RADARR_API_KEY`: API key for Radarr authentication
- `CLAUDE_API_KEY`: API key for Claude AI
- `DEBUG_LOGGING`: Boolean flag to enable detailed logging (default: false)
- `SMTP_SERVER`: SMTP server address
- `SMTP_PORT`: SMTP port (default: 25)
- `NOTIFICATION_RECIPIENTS`: Comma-separated list of email recipients
- `SCHEDULE_INTERVAL`: Parsable time interval (e.g., "1h", "1d", "1w", "1mo")
- `SCHEDULE_START_TIME`: Start time in 24hr format (e.g., "03:00")
- `TZ`: Time zone for scheduling (default: UTC)

### Docker Volume
- Mount point for Kometa configuration: `/app/kometa-config`

## Scheduling
- The script will manage its own scheduling
- Sleep between intervals using the configured schedule
- Log next execution time after each run

## Tagging Convention
- All AI-managed tags will use prefix `KAI-`
- Format: `KAI-<collection-name>`
- Examples:
  - `KAI-film-noir`
  - `KAI-heist-movies`
  - `KAI-romcom`

## Collection Configuration
Extend Kometa's existing collection definition files with special comment blocks placed above the collection name:

```yaml
# Regular Kometa collection definition
collections:
  # === KOMETA-AI ===
  # enabled: true
  # prompt: |
  #   Identify film noir movies based on these criteria:
  #   - Made primarily between 1940-1959
  #   - Dark, cynical themes and moral ambiguity
  #   - Visual style emphasizing shadows, unusual angles
  #   - Crime or detective storylines
  #   - Femme fatale character often present
  # confidence_threshold: 0.7
  # === END KOMETA-AI ===
  Film Noir:
    plex_search:
      all:
        genre: Film-Noir
    # ... existing Kometa config ...
```

## Notification System
- Simple SMTP-based email notifications
- Default: redirect to postfix on port 25
- Summary email includes:
  - Changes by collection (added/removed movies)
  - Total number of changes
  - Any errors encountered
  - Next scheduled run time

## Error Handling
- Retries for temporary API failures with exponential backoff (starting ~1s, max ~30s)
- Maximum of 5-10 retry attempts before moving to next collection
- Graceful degradation if Radarr or Claude APIs are unavailable
- Complete error context in notifications (primary failsafe mechanism)
- Detailed logging of all API interactions and decisions
- Option to manually trigger re-run via API endpoint

### Specific Error Handling Strategies
- **API Connection Failures**:
  - Radarr API unavailable:
    - Log detailed connection error
    - Retry with exponential backoff
    - After max retries, abort entire run and notify
    - Include network diagnostics in notification
  - Claude API unavailable:
    - Log detailed error information
    - Retry with exponential backoff
    - After max retries, skip current collection
    - Continue processing other collections
    - Note failed collections in summary email

- **Data Processing Errors**:
  - Invalid Kometa configuration:
    - Log specific parsing errors
    - Skip affected collections
    - Include detailed error in notifications
    - Continue processing valid collections
  - Claude response parsing failures:
    - Attempt multiple parsing strategies
    - Log raw response for debugging
    - If unable to parse, skip current collection
    - Include failure details in notification

- **State Management Errors**:
  - State file corruption:
    - Log error details
    - Attempt to restore from backup
    - If backup restoration fails, create new state
    - Include alert in notification
  - State file write failures:
    - Log error details
    - Retry with exponential backoff
    - If write still fails, continue execution
    - Include alert in notification

- **Runtime Errors**:
  - Memory limit exceeded:
    - Implement chunk-based processing of large movie lists
    - Process collections sequentially if memory pressure detected
    - Log memory usage statistics
  - Execution timeout:
    - Save partial progress
    - Resume from saved point on next execution
    - Include timeout information in notification

- **Error Reporting**:
  - Include stack traces in log files (not in emails)
  - Group related errors in notifications
  - Include timestamp, affected collection, and movie details
  - Provide troubleshooting information where possible

## Security Considerations
- All API keys stored as environment variables, not in code
- No persistent storage of API responses
- Minimal permission requirements for Radarr API
- Validation of all API responses before processing

## Implementation & Deployment
- Implement proper rate limiting for Claude API
- Include dry-run mode for testing
- Maintain detailed logs for troubleshooting
- Store state between runs for change detection
- Validate API calls to radarr and claude using API documentation, schemas when available
- Store state in a location mapped via a docker volume for persistence through restarts
- Document code using comments and update the repo readme with usage documentation, kometa comment syntax, sample docker compose yaml, and a detailed description of how the script functions

### Docker-First Approach
- **Production Dockerfile**:
  ```dockerfile
  FROM python:3.11-slim-bullseye

  WORKDIR /app

  # Install dependencies
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  # Copy application code
  COPY . .

  # Create mount points for volumes
  VOLUME ["/app/kometa-config", "/app/state", "/app/logs"]

  # Set default environment variables
  ENV TZ=UTC \
      SCHEDULE_INTERVAL=1d \
      SCHEDULE_START_TIME=03:00 \
      DEBUG_LOGGING=false \
      SMTP_PORT=25

  # Entry point runs the main script
  ENTRYPOINT ["python", "-m", "kometa_ai"]
  ```

- **Development Dockerfile (Dockerfile.dev)**:
  ```dockerfile
  FROM python:3.11-slim-bullseye

  WORKDIR /app

  # Install development dependencies
  COPY requirements.txt requirements-dev.txt ./
  RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

  # Don't copy application code - it will be mounted as volume
  # for hot reloading during development

  # Create mount points for volumes
  VOLUME ["/app", "/app/kometa-config", "/app/state", "/app/logs"]

  # Set default environment variables for development
  ENV TZ=UTC \
      SCHEDULE_INTERVAL=1d \
      SCHEDULE_START_TIME=03:00 \
      DEBUG_LOGGING=true \
      PYTHONASYNCIODEBUG=1 \
      PYTHONDONTWRITEBYTECODE=1 \
      PYTHONUNBUFFERED=1

  # Use watchdog for auto-reloading during development
  RUN pip install watchdog[watchmedo]
  
  # Entry point with auto-reload (dev only)
  ENTRYPOINT ["watchmedo", "auto-restart", "--directory=./", "--pattern=*.py", "--recursive", "--", "python", "-m", "kometa_ai"]
  ```

- **Docker Healthcheck**:
  ```dockerfile
  HEALTHCHECK --interval=5m --timeout=30s --start-period=1m --retries=3 \
    CMD python -m kometa_ai --health-check || exit 1
  ```

- **Container Startup Sequence**:
  1. Initialize logging
  2. Load configuration from environment variables
  3. Verify connectivity to Radarr API
  4. Validate Claude API key
  5. Calculate next run time based on schedule parameters
  6. Enter sleep until next scheduled run
  7. Log startup information including next run time

### CLI Interface
- **Command Line Options**:
  ```
  Usage: python -m kometa_ai [OPTIONS]

  Options:
    --run-now                Run immediately instead of waiting for schedule
    --dry-run                Perform all operations without making actual changes
    --collection TEXT        Process only the specified collection
    --batch-size INTEGER     Override default batch size
    --force-refresh          Reprocess all movies, ignoring cached decisions
    --health-check           Run internal health check and exit
    --dump-config            Print current configuration and exit
    --dump-state             Print current state file and exit
    --reset-state            Clear state file and start fresh
    --version                Show version information and exit
    --help                   Show this message and exit
  ```

- **Manual Execution**:
  ```bash
  docker exec kometa-ai python -m kometa_ai --run-now
  ```

- **Viewing Logs**:
  ```bash
  docker logs kometa-ai
  ```

- **Schedule Management**:
  - Upon start, calculate next run time from SCHEDULE_INTERVAL and SCHEDULE_START_TIME
  - If container starts after the scheduled time, wait until next period
  - Log countdown to next execution in debug mode
  - Support both cron-style and interval-based scheduling

### Version Management
- **Version Information**:
  - Store version in `__version__.py` file
  - Include git commit hash in builds if available
  - Store version in state file to handle state format migrations
  - Version check during startup to ensure state compatibility

- **State Version Handling**:
  ```json
  {
    "version": "0.1.0",
    "state_format_version": 1,
    "last_update": "2025-04-28T12:00:00Z",
    "decisions": {...}
  }
  ```
  
- **Update Flow**:
  - Check state_format_version against current expected version
  - Run migrations if necessary
  - Fail with clear error if incompatible
  
### Code Quality & Testing Standards
- **Type Hints & Static Analysis**:
  - Use type hints throughout codebase
  - Integrate mypy for static type checking
  - Configure strict mode to catch type errors early
  - Include type checking in CI/CD pipeline

- **Code Style & Linting**:
  - Use Black for consistent code formatting
  - Use isort for import sorting
  - Implement flake8 for linting
  - Configure pre-commit hooks for automated style enforcement

- **Testing Framework**:
  - Pytest as primary test framework
  - Structure tests by module/component
  - Mock external dependencies (Radarr API, Claude API)
  - Use fixtures for common test setups
  - Target minimum 90% code coverage

- **Test Data**:
  - Create sample Kometa configuration files
  - Generate mock movie data covering edge cases
  - Include regression test cases
  - Record and replay API responses for consistent testing

### Monitoring & Resilience
- **Structured Logging**:
  - Use JSON formatted logs for machine-readability
  - Include consistent fields for correlation (run_id, collection_name)
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Rotate log files to prevent disk space issues

- **Metrics Collection**:
  - Track run duration for overall execution and per collection
  - Count API calls to Radarr and Claude
  - Measure batch processing times
  - Count tag changes (adds, removes)

- **Resilience Features**:
  - Graceful handling of container termination
  - State checkpointing during long-running operations
  - Auto-resume from last known good state
  - Signal handling for clean shutdown

- **Failure Recovery**:
  - Store last successful run information
  - Track partial progress for interrupted runs
  - Back up state file before modifications
  - Implement state file rotation (keep last 5 versions)

## Technical Design

### Code Organization

```
/app
├── main.py               # Entry point, scheduling logic
├── config.py             # Configuration management
├── radarr/
│   ├── __init__.py
│   ├── client.py         # Radarr API client
│   └── models.py         # Movie and tag data models
├── claude/
│   ├── __init__.py
│   ├── client.py         # Claude API client
│   └── prompts.py        # Prompt templates and formatting
├── kometa/
│   ├── __init__.py
│   ├── parser.py         # Kometa YAML parser
│   └── models.py         # Collection configuration models
├── state/
│   ├── __init__.py
│   ├── manager.py        # State persistence
│   └── models.py         # State data models
├── notification/
│   ├── __init__.py
│   ├── email.py          # Email notification system
│   └── formatter.py      # Notification content formatting
└── utils/
    ├── __init__.py
    ├── logging.py        # Logging configuration
    ├── scheduling.py     # Scheduling utilities
    └── helpers.py        # General utility functions
```

### Development Stages

#### Stage 1: Core Infrastructure and Docker Setup (2-3 weeks)
- **Focus**: Basic functionality in Docker environment
- **Components**:
  - Docker infrastructure setup:
    - Basic Dockerfile
    - Docker Compose for development
    - Volume mounts for configs and state
    - Hot reloading for development
  - Configuration loading (environment variables)
  - Radarr API client (read-only)
  - Basic YAML parsing for Kometa collections
  - Logging setup
  - Simple state management (file read/write)
  - CLI interface for testing
  - Health checks
  - Unit tests for each component

- **Docker Dev Environment**:
  - Docker Compose file for development:
    ```yaml
    version: '3'
    services:
      kometa-ai:
        build: 
          context: .
          dockerfile: Dockerfile.dev
        volumes:
          - ./:/app
          - ./test_data/kometa-config:/app/kometa-config
          - ./test_data/state:/app/state
          - ./logs:/app/logs
        environment:
          - RADARR_URL=http://mock-radarr:7878
          - RADARR_API_KEY=dev_api_key
          - CLAUDE_API_KEY=dev_api_key
          - DEBUG_LOGGING=true
        command: ["--run-now", "--dry-run"]
      
      mock-radarr:
        image: mockserver/mockserver
        ports:
          - "7878:1080"
        volumes:
          - ./test_data/mock_radarr:/mockserver/mockserver_expectations
    ```

- **Testing**:
  - Test inside Docker environment
  - Mock Radarr API responses using MockServer
  - Sample Kometa YAML files mounted as volume
  - Verify configuration parsing
  - Test state file read/write
  - Validate volume mounting
  - Test CLI interface

#### Stage 2: Radarr Integration (1 week)
- **Focus**: Complete Radarr interaction
- **Components**:
  - Tag management (read/write)
  - Movie metadata retrieval
  - Tag application logic
  - Change detection (metadata hash)
  - Integration tests with Radarr

- **Testing**:
  - Test against development Radarr instance
  - Verify tag creation/application
  - Test metadata hash calculation
  - Ensure idempotent operations

#### Stage 3: Claude Integration (1-2 weeks)
- **Focus**: AI-based classification
- **Components**:
  - Claude API client
  - Prompt formatting
  - Response parsing
  - Decision storage
  - Rate limiting implementation
  - Batched processing

- **Testing**:
  - Small-scale tests with real Claude API
  - Verify prompt generation
  - Test response parsing
  - Validate decision caching

#### Stage 4: Full Pipeline (1 week)
- **Focus**: End-to-end workflow
- **Components**:
  - Scheduling
  - Email notifications
  - Error handling
  - Full state persistence
  - Incremental processing

- **Testing**:
  - End-to-end tests with small dataset
  - Verify email notifications
  - Test scheduled execution
  - Validate incremental processing

#### Stage 5: Performance and Scaling (1 week)
- **Focus**: Handle large libraries
- **Components**:
  - Optimize batch size
  - Improve memory usage
  - Enhance error recovery
  - Performance profiling

- **Testing**:
  - Load tests with large movie datasets
  - Memory usage monitoring
  - Error injection testing

#### Stage 6: Production Deployment (1 week)
- **Focus**: Production readiness and documentation
- **Components**:
  - Production Dockerfile optimization
  - Comprehensive documentation
  - Sample configuration templates
  - Final integration tests
  - Deployment guide

- **Testing**:
  - Test production container builds
  - End-to-end deployment test
  - Backward compatibility verification
  - Performance benchmarking

### Testing Strategy

- **Unit Tests**: For all core components
  - Use pytest framework
  - Mock external dependencies
  - Test edge cases and error handling

- **Integration Tests**: For API interactions
  - Test against development instances of Radarr
  - Use Claude API with minimal calls
  - Verify correct data flow between components

- **End-to-End Tests**:
  - Test complete workflow with small dataset
  - Validate correct tag application
  - Test notification delivery
  - Verify state persistence

- **Dry Run Mode**:
  - Implement a dry run mode that logs actions without performing them
  - Use for validation before applying changes

### Incremental Deployment

1. Start with a small subset of collections (1-2)
2. Run with dry-run mode enabled
3. Verify expected tag changes
4. Enable for a single collection in production
5. Gradually add more collections
6. Scale to full library

## Detailed Implementation Specifications

### Claude API Integration
- **API Interaction Model**:
  - Use Anthropic's official Python client library
  - Seek out and use the library documentation to author against
  - Set up message context with system prompt explaining the task
  - Use Claude 3 Opus or Sonnet for best quality categorization
  - Structure prompts to encourage consistent JSON output format
  - Implement batched processing to handle large movie libraries (5,000-10,000+ movies)

- **Prompt Design**:
  - System prompt explaining the movie categorization task
  - User prompt containing:
    - Collection definition and criteria
    - Custom prompt from collection configuration
    - Complete movie list with relevant attributes
    - Explicit request for JSON-formatted response with movie IDs/decisions

- **System Prompt**:
  ```
  You are a film expert tasked with categorizing movies for a Plex media server. Your job is to determine which movies belong in a specific collection based on the provided criteria.

  Guidelines:
  1. Focus on the specific collection definition provided
  2. Consider all relevant movie attributes (title, year, genres, plot, directors, actors, etc.)
  3. Apply the collection criteria consistently
  4. Provide a confidence score (0.0-1.0) for each decision
  5. When uncertain, provide reasoning in your response
  6. Return answers in valid JSON format only

  You'll receive a collection definition with criteria and a list of movies to evaluate. For each movie, decide if it belongs in the collection and provide your confidence level.

  Your response must follow this exact JSON format:
  {
    "collection_name": "Name of the collection",
    "decisions": [
      {
        "movie_id": 123,
        "title": "Movie Title",
        "include": true/false,
        "confidence": 0.95,
        "reasoning": "Optional explanation for borderline cases"
      },
      // Additional movies...
    ]
  }

  Do not include any text outside of this JSON structure. Your JSON must be valid and properly formatted.
  ```

- **Sample Collection Configuration Prompt**:
  ```
  I need you to categorize movies for the "Film Noir" collection.

  COLLECTION DEFINITION AND CRITERIA:
  Film Noir is a style or genre of cinematographic film marked by a mood of pessimism, fatalism, and menace. The term was popularized by French critics who noticed a trend of darkness and downbeat themes in many American crime and detective films released in France after World War II.
  
  Identify film noir movies based on these criteria:
  - Made primarily between 1940-1959
  - Dark, cynical themes and moral ambiguity
  - Visual style emphasizing shadows, unusual angles
  - Crime or detective storylines
  - Femme fatale character often present
  
  Additional criteria:
  - Include neo-noir films from later periods only if they strongly exemplify classic noir characteristics
  - Prioritize black and white films over color
  - Consider director history - prioritize films by directors known for noir (Billy Wilder, Fritz Lang, etc.)

  For each movie in the provided list, evaluate whether it belongs in the Film Noir collection based on these criteria. Provide your decision and a confidence level (0.0-1.0) for each movie. Return your evaluation in the required JSON format.
  ```

- **Response Parsing**:
  - Validate response structure before processing
  - Extract JSON sections from Claude response
  - Fall back to regex parsing if JSON extraction fails
  - Handle partial results if processing gets interrupted

- **Incremental Processing for Large Libraries**:
  - **Initial Collection Processing**:
    - First run of a new collection requires evaluating all movies
    - Process in batches (100-300 movies per batch) to stay within API limits
    - Store all decisions (movie ID, collection, include/exclude, confidence) in state JSON
    - Seek out and use Radarr API documentation (schema if avaialble) to author against
    
  - **Subsequent Optimized Runs**:
    - Only send to Claude:
      - New movies added since last run
      - Movies with significantly changed metadata
      - Movies previously near the confidence threshold (0.6-0.8)
    - Reuse previous decisions for all other movies
    - This approach dramatically reduces API costs after initial setup
    
  - **Decision Persistence**:
    - Each movie-collection decision is stored with:
      - Movie ID and metadata hash
      - Include/exclude decision
      - Confidence score
      - Timestamp of decision
      - Claude's reasoning (for borderline cases)
    - State file grows with library but remains manageable even for large collections

- **Rate Limit Handling**:
  - Track API usage throughout execution
  - Implement token counting to stay within limits
  - Exponential backoff starting at 1s, maximum 30s delay
  - If rate limit persists beyond 10 attempts, store state and abort current collection
  - Resume from stored state on next execution

### State Management
- **State Storage Format**:
  - Use JSON for state persistence
  - Store in mounted volume at `/app/state/kometa_state.json`
  - Include version field to support future format changes
  
- **Stored State Components**:
  - Last successful run timestamp
  - Per-collection processing status
  - Last processed movie ID for each collection
  - Current Radarr movie list snapshot hash
  - Tag change history (limited to last 100 changes)
  - Error counters and last error details
  - **Decision cache**: Complete history of all Claude decisions:
    ```json
    "decisions": {
      "movie:1234": {
        "metadata_hash": "a1b2c3...",
        "collections": {
          "film-noir": {
            "tag": "KAI-film-noir",
            "include": true,
            "confidence": 0.92,
            "timestamp": "2025-04-28T14:30:00Z",
            "reasoning": "Classic noir elements present..."
          },
          "crime-movies": {
            "tag": "KAI-crime-movies",
            "include": true,
            "confidence": 0.87,
            "timestamp": "2025-04-28T14:35:00Z"
          }
        }
      }
    }
    ```
  
- **State Recovery**:
  - Check for existing state file on startup
  - Validate state file integrity
  - Compare stored movie list hash with current Radarr data
  - If movie list significantly changed, trigger full reprocessing
  - Otherwise, resume from last processed point

- **Change Detection**:
  - Track tag changes between runs
  - Store before/after tag states for reporting
  - Use hash comparison to detect movie metadata changes:
    ```python
    # Example metadata hash calculation
    def calculate_metadata_hash(movie):
        # Include only fields relevant to classification
        metadata = {
            'title': movie['title'],
            'year': movie['year'],
            'plot': movie['plot'],
            'genres': sorted(movie['genres']),
            'directors': sorted(movie['directors']),
            'actors': sorted(movie['actors'][:5] if len(movie['actors']) > 5 else movie['actors'])
        }
        # Create deterministic JSON string and hash it
        metadata_json = json.dumps(metadata, sort_keys=True)
        return hashlib.sha256(metadata_json.encode('utf-8')).hexdigest()
    ```
  - Compare current metadata hash with stored hash
  - If hash changed, movie needs reevaluation
  - Prioritize reprocessing for movies with metadata changes

### Tag Reconciliation Logic
- **Tag Management Principles**:
  - Only manage tags with the `KAI-` prefix
  - Never modify or remove manually assigned tags
  - Apply the principle of least surprise (minimize unexpected changes)
  - **Movies will commonly belong to multiple collections** - this is expected and desired

- **Tag Application Rules**:
  - Each collection has a corresponding tag: `KAI-<collection-slug>`
  - Slugify collection names (lowercase, replace spaces with hyphens)
  - Apply tags based on Claude's confidence score and threshold
  - For multi-word collection names, use hyphens (e.g., `KAI-sci-fi-comedy`)
  - Apply multiple collection tags whenever appropriate (e.g., a movie can have both `KAI-heist-movies` and `KAI-crime`)

- **Reconciliation Process**:
  - For each movie, get current tags from Radarr
  - Identify AI-managed tags (prefix `KAI-`)
  - Compare Claude's recommendations with current tags
  - Calculate changes (additions and removals)
  - Apply confidence threshold filter
  - Execute API calls to update tags
  - Never remove a tag just because a movie was added to another collection

- **Multi-Collection Handling**:
  - Movies are expected and encouraged to be in multiple collections
  - Each collection evaluation happens independently
  - No limit on how many collections a movie can belong to
  - No "exclusivity" between collections by default
  - Optional exclusivity can be configured via `exclude_tags` parameter

- **Confidence Handling**:
  - If confidence scores conflict, prefer higher confidence
  - When scores are equal, maintain existing tags (status quo bias)
  - Log detailed reasoning for borderline decisions

### Collection Parsing
- **File Discovery**:
  - Scan `/app/kometa-config` directory recursively
  - Parse all `.yml` and `.yaml` files
  - Skip files prefixed with underscore (`_`) or dot (`.`)

- **Comment Block Extraction**:
  - Identify special comment blocks between markers:
    ```yaml
    # === KOMETA-AI ===
    # ...configuration...
    # === END KOMETA-AI ===
    ```
  - Associate comment blocks with their parent collection
  - Support multi-file collections (same collection in multiple files)

- **Configuration Parameters**:
  - `enabled`: Boolean flag to enable/disable collection (default: false)
  - `prompt`: Custom prompt text for this collection
  - `confidence_threshold`: Minimum confidence score (0.0-1.0, default: 0.7)
  - `priority`: Processing priority (higher = earlier, default: 0)
  - `exclude_tags`: List of tags that exclude movies from this collection
  - `include_tags`: List of tags that automatically include movies

- **YAML Parsing Logic**:
  - Use Python's ruamel.yaml for comment-preserving parsing
  - Extract collection configuration from comments
  - Convert comment indentation to proper YAML
  - Parse into structured configuration objects
  - Validate against schema before processing
  
## Future Extensions
- Support for other media types (TV shows via Sonarr)
- Enhanced confidence scoring and manual review workflow
- Webhook notifications (Discord, Slack, etc.)
- Web UI for monitoring and manual control
- Integration with other media managers beyond Radarr
- Advanced scheduling with blackout periods
- Multiple AI provider support (OpenAI, etc.)

