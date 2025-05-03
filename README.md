# Kometa-AI
[![Kometa-AI CI/CD](https://github.com/tikibozo/kometa-ai/actions/workflows/kometa-ci-cd.yml/badge.svg?branch=main)](https://github.com/tikibozo/kometa-ai/actions/workflows/kometa-ci-cd.yml)

Kometa-AI integrates Claude AI into Kometa to intelligently select movies for collections based on natural language prompts rather than just metadata tags.

## Overview

Kometa-AI is a production-ready, dockerized Python application that:

1. Queries Radarr for movies, metadata, and tags
2. Examines AI-tagged collections in Kometa configuration
3. Evaluates movies using Claude AI against provided prompts
4. Updates tags in Radarr accordingly

Kometa can then consume this output as a standard Radarr tag collection, creating a bridge between Radarr's tagging system and Kometa's collection management.

## Features

- **AI-Powered Classification**: Leverage Claude AI to intelligently categorize movies based on sophisticated criteria
- **Easy Configuration**: Define collections using natural language prompts via special comment blocks in Kometa YAML files
- **Efficient Processing**: Optimized for large movie libraries with incremental processing and batching
- **Automatic Scheduling**: Self-managed scheduling based on configurable intervals
- **Email Notifications**: Comprehensive email reports of changes and errors
- **Performance Optimization**: Memory-efficient design for libraries of any size
- **Production-Ready Deployment**: Complete Docker-based deployment with security best practices

## How It Works

1. **Configuration**: AI collections are defined in standard Kometa YAML files using special comment blocks
2. **Tagging Convention**: All AI-managed tags use the prefix `KAI-` (e.g., `KAI-film-noir`)
3. **Scheduling**: The script manages its own scheduling based on environment variables
4. **Notifications**: Email notifications summarize changes and errors

## Collection Configuration

Extend Kometa's existing collection definition files with special comment blocks placed above the collection name:

```yaml
collections:
  # === KOMETA-AI ===
  # enabled: true
  # confidence_threshold: 0.7
  # prompt: |
  #   Identify film noir movies based on these criteria:
  #   - Made primarily between 1940-1959
  #   - Dark, cynical themes and moral ambiguity
  #   - Visual style emphasizing shadows, unusual angles
  #   - Crime or detective storylines
  #   - Femme fatale character often present
  # === END KOMETA-AI ===
  Film Noir:
    plex_search:
      all:
        genre: Film-Noir
    # ... existing Kometa config ...
```

Many example collections are provided in the `config-examples` directory.

## Installation and Deployment

### Quick Start

1. Clone the repository
2. Create configuration directories:
   ```bash
   mkdir -p kometa-ai/{kometa-config,state,logs}
   ```
3. Copy your Kometa collection configuration files to `kometa-ai/kometa-config/`
4. Edit `docker-compose.yml` with your environment variables
5. Start the container:
   ```bash
   docker-compose up -d
   ```

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Environment Variables

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

See [DEPLOYMENT.md](DEPLOYMENT.md) for the complete list of configuration options.

## Docker Deployment

```yaml
version: '3'
services:
  kometa-ai:
    image: kometa-ai:latest
    container_name: kometa-ai
    volumes:
      - ./kometa-config:/app/kometa-config
      - ./state:/app/state
      - ./logs:/app/logs
    environment:
      - RADARR_URL=http://radarr:7878
      - RADARR_API_KEY=your_api_key
      - CLAUDE_API_KEY=your_claude_api_key
      - DEBUG_LOGGING=false
      - SMTP_SERVER=smtp.example.com
      - NOTIFICATION_RECIPIENTS=user@example.com
      - SCHEDULE_INTERVAL=1d
      - SCHEDULE_START_TIME=03:00
      - TZ=America/New_York
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-m", "kometa_ai", "--health-check"]
      interval: 5m
      timeout: 30s
      retries: 3
      start_period: 1m
```

## Command Line Options

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
  --profile                Enable performance profiling
  --optimize-batch-size    Run batch size optimization test
  --memory-profile         Run with detailed memory profiling
  --version                Show version information and exit
  --help                   Show this message and exit
```

## Development

For development setup and guidelines, see [DEVELOPMENT.md](DEVELOPMENT.md).

1. Set up the development environment:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```
2. Run tests:
   ```bash
   docker exec kometa-ai pytest
   ```

## Documentation

- [DESIGN.md](DESIGN.md) - Detailed design and architecture specifications
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide and configuration reference
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development setup and guidelines
- [config-examples/](config-examples/) - Example collection configurations

## Project Status

This project has completed all planned development stages and is now production-ready.

- ✅ Stage 1: Core Infrastructure and Docker Setup
- ✅ Stage 2: Radarr Integration
- ✅ Stage 3: Claude Integration
- ✅ Stage 4: Full Pipeline
- ✅ Stage 5: Performance and Scaling
- ✅ Stage 6: Production Deployment
