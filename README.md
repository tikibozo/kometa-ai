# Kometa-AI
[![Kometa-AI CI/CD](https://github.com/tikibozo/kometa-ai/actions/workflows/kometa-ci-cd.yml/badge.svg?branch=main)](https://github.com/tikibozo/kometa-ai/actions/workflows/kometa-ci-cd.yml)

Kometa-AI integrates [Claude AI](https://claude.ai) as a pre-processor of [Kometa](https://kometa.wiki/) configurations to intelligently select movies for collections based on natural language prompts.

## Overview

Kometa-AI is a dockerized Python application that:
1. Examines your existing Kometa configuration looking for AI-tagged collections
2. Queries your existing Radarr instance for movies
3. Asks Claude to evaluate if each movie should be in the defined collection based on the provided prompt
4. Updates tags in Radarr accordingly so Kometa can do the actual collection updating in Plex

In short, once you set this up you can simply add a Radarr collection (with a special comment block) to your Kometa config, Kometa-AI will run, then the next time Kometa runs it will populate the collection in Plex. 

**This project is not associated with Kometa directly**, I'm just a fan. This is also explicitly designed to not interfere with Kometa's processing in any way - it just looks at the configuration, and then puts data in Radarr so Kometa can use it.

## Collection Configuration
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
    radarr_taglist: KAI-film-noir

    # ... existing Kometa config ...
```

There are more example collections in the `config-examples` directory.

## But why though? What problem does this solve?
So I started off giving Claude my Radarr db and the kometa community repo, and asked it to come up with ideas for collections (try it! it's fun.) It came up with some really great ideas for collections! However implementing these interesting collections meant figuring out either a metadata scheme (between x release dates from y directors, etc.) or trying to find someone who had already done the work to build the movie list and created an imdb list (or similar.) Some of the collections worked fine this way, but for others I needed a way to have Claude decide which movies should be in the interesting new collection we came up with. 

So that's what this does - give it some interesting collection name/prompt, and it'll figure out which of your movies should be in it. The possibilties are endless!

## This thing costs money (unless you have a Claude subscription)
Kometa-AI supports two Claude backends:

- **`CLAUDE_BACKEND=api`** (default): calls the Anthropic API with a `CLAUDE_API_KEY`. This bills per token — it won't cost much (the app reports actual costs per run), but it is real money and separate from a chat subscription. See [Claude Console](https://console.anthropic.com/settings/keys) to create an API key.
- **`CLAUDE_BACKEND=cli`**: shells out to the [Claude Code CLI](https://claude.com/claude-code) using whatever it's logged in with — typically a Claude subscription, so runs don't bill per token. The container downloads the CLI automatically on first start when this backend is selected. Authenticate either way:
  - **`CLAUDE_CODE_OAUTH_TOKEN` env var** (recommended for containers): generate a long-lived token with `claude setup-token` on a logged-in machine and pass it as an environment variable — no volume mount needed.
  - **Credentials mount**: mount your `~/.claude` directory at `/app/.claude`.

  Cost lines logged with the `cli` backend are the CLI's notional API-equivalent cost; subscription usage isn't billed per token.

Either way, Kometa-AI saves results, so unless you change the collection or movie definition, it won't re-evaluate each movie against each collection on each run. Once the first run of a given collection is completed, it'll just send up new or changed movies for evaluation.

> **Upgrading from a pre-2026 version?** Evaluations now include Radarr's TMDB keywords, certification, language, and ratings, which counts as a metadata change — the first run after upgrading re-evaluates your whole library once (existing decisions are used as anchors, so membership stays stable).

## Features

- **AI-Powered Classification**: Leverage Claude AI to intelligently categorize movies based on sophisticated criteria
- **Easy Configuration**: Define collections using natural language prompts via special comment blocks in Kometa YAML files
- **Efficient Processing**: Optimized for large movie libraries with incremental processing and batching
- **Automatic Scheduling**: Self-managed scheduling based on configurable intervals
- **Email Notifications**: Comprehensive email reports of changes and errors
- **Performance Optimization**: Memory-efficient design for libraries of any size
- **Production-Ready Deployment**: Complete Docker-based deployment with security best practices
- **Tag Consistency**: Automatic detection and optional correction of mismatched radarr_taglist values

## How It Works

1. **Configuration**: AI collections are defined in standard Kometa YAML files using special comment blocks
2. **Tagging Convention**: All AI-managed tags use the prefix `KAI-` (e.g., `KAI-film-noir`)
3. **Scheduling**: The script manages its own scheduling based on environment variables
4. **Notifications**: Email notifications summarize changes and errors

## Installation and Deployment

### Docker Deployment

```yaml
services:
  kometa-ai:
    image: tikibozo/kometa-ai:latest
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
      - KOMETA_FIX_TAGS=false
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-m", "kometa_ai", "--health-check"]
      interval: 5m
      timeout: 30s
      retries: 3
      start_period: 1m
```

### Environment Variables

- `RADARR_URL`: Base URL for Radarr instance
- `RADARR_API_KEY`: API key for Radarr authentication
- `CLAUDE_BACKEND`: `api` (Anthropic API key, default) or `cli` (Claude Code CLI / subscription)
- `CLAUDE_API_KEY`: API key for Claude AI (required for the `api` backend)
- `CLAUDE_MODEL`: Optional override for Claude model (default: claude-sonnet-5)
- `DEBUG_LOGGING`: Boolean flag to enable detailed logging (default: false)
- `SMTP_SERVER`: SMTP server address
- `SMTP_PORT`: SMTP port (default: 25)
- `NOTIFICATION_RECIPIENTS`: Comma-separated list of email recipients
- `SCHEDULE_INTERVAL`: Parsable time interval (e.g., "1h", "1d", "1w", "1mo")
- `SCHEDULE_START_TIME`: Start time in 24hr format (e.g., "03:00")
- `TZ`: Time zone for scheduling (default: UTC)
- `KOMETA_FIX_TAGS`: Boolean flag to automatically fix mismatched radarr_taglist values (default: false)

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Command Line Options

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
