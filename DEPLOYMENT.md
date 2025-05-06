# Kometa-AI Deployment Guide

This guide provides detailed instructions for deploying Kometa-AI in a production environment. It covers system requirements, installation steps, configuration options, and best practices for deployment and maintenance.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation Methods](#installation-methods)
3. [Docker Deployment](#docker-deployment)
4. [Configuration](#configuration)
5. [Volume Management](#volume-management)
6. [Security Considerations](#security-considerations)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Backup and Restore](#backup-and-restore)
9. [Upgrading](#upgrading)
10. [Troubleshooting](#troubleshooting)
11. [Performance Tuning](#performance-tuning)
12. [Integration with Kometa](#integration-with-kometa)

## System Requirements

### Minimum Requirements
- Docker Engine 20.10.0 or higher
- 1 GB RAM (minimum)
- 2 GB disk space
- Network access to Radarr API
- Internet access for Claude API

### Recommended Requirements
- Docker Engine 23.0.0 or higher
- 2 GB RAM (for libraries up to 5,000 movies)
- 4 GB RAM (for libraries over 5,000 movies)
- 5 GB disk space (for logs and state)
- Fast, reliable internet connection

### API Keys Required
- Radarr API key
- Claude API key

## Installation Methods

Kometa-AI can be installed using Docker or directly from source. The recommended method is using Docker for simplicity and isolation.

## Docker Deployment

### Using Docker Compose (Recommended)

1. Create a deployment directory:
   ```bash
   mkdir -p kometa-ai/{kometa-config,state,logs}
   cd kometa-ai
   ```

2. Create a `docker-compose.yml` file:
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
         - RADARR_API_KEY=your_radarr_api_key
         - CLAUDE_API_KEY=your_claude_api_key
         - DEBUG_LOGGING=false
         - SCHEDULE_INTERVAL=1d
         - SCHEDULE_START_TIME=03:00
         - TZ=America/New_York
         - SMTP_SERVER=smtp.example.com
         - SMTP_PORT=587
         - SMTP_USERNAME=your_username
         - SMTP_PASSWORD=your_password
         - SMTP_USE_TLS=true
         - NOTIFICATION_RECIPIENTS=user@example.com
         - NOTIFICATION_FROM=kometa-ai@example.com
       restart: unless-stopped
       healthcheck:
         test: ["CMD", "python", "-m", "kometa_ai", "--health-check"]
         interval: 5m
         timeout: 30s
         retries: 3
         start_period: 1m
       networks:
         - kometa-network
   
   networks:
     kometa-network:
       external: true
   ```

3. Edit the file to replace placeholder values with your actual configuration.

4. Build and start the container:
   ```bash
   docker-compose up -d
   ```

### Using Docker Run Command

Alternatively, you can use the Docker run command directly:

```bash
docker run -d \
  --name=kometa-ai \
  -e RADARR_URL=http://radarr:7878 \
  -e RADARR_API_KEY=your_radarr_api_key \
  -e CLAUDE_API_KEY=your_claude_api_key \
  -e SCHEDULE_INTERVAL=1d \
  -e SCHEDULE_START_TIME=03:00 \
  -e TZ=America/New_York \
  -e SMTP_SERVER=smtp.example.com \
  -e SMTP_PORT=587 \
  -e SMTP_USERNAME=your_username \
  -e SMTP_PASSWORD=your_password \
  -e SMTP_USE_TLS=true \
  -e NOTIFICATION_RECIPIENTS=user@example.com \
  -e NOTIFICATION_FROM=kometa-ai@example.com \
  -v /path/to/kometa-config:/app/kometa-config \
  -v /path/to/state:/app/state \
  -v /path/to/logs:/app/logs \
  --restart unless-stopped \
  kometa-ai:latest
```

### Building the Docker Image

If you need to build the image yourself:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/kometa-ai.git
   cd kometa-ai
   ```

2. Build the Docker image:
   ```bash
   docker build -t kometa-ai:latest .
   ```

3. Use either of the deployment methods above with your locally built image.

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `RADARR_URL` | Base URL for Radarr instance | | Yes |
| `RADARR_API_KEY` | API key for Radarr | | Yes |
| `CLAUDE_API_KEY` | API key for Claude AI | | Yes |
| `SCHEDULE_INTERVAL` | Interval between runs (e.g., "1h", "1d", "1w", "1mo") | "1d" | No |
| `SCHEDULE_START_TIME` | Start time in 24hr format (e.g., "03:00") | "03:00" | No |
| `TZ` | Time zone for scheduling | UTC | No |
| `DEBUG_LOGGING` | Enable detailed logging | false | No |
| `SMTP_SERVER` | SMTP server address | | No |
| `SMTP_PORT` | SMTP server port | 25 | No |
| `SMTP_USERNAME` | SMTP username for authentication | | No |
| `SMTP_PASSWORD` | SMTP password for authentication | | No |
| `SMTP_USE_TLS` | Enable TLS for SMTP | false | No |
| `SMTP_USE_SSL` | Enable SSL for SMTP | false | No |
| `NOTIFICATION_RECIPIENTS` | Comma-separated list of email recipients | | No |
| `NOTIFICATION_FROM` | Email sender address | "kometa-ai@localhost" | No |
| `NOTIFICATION_REPLY_TO` | Reply-to email address | Same as FROM | No |
| `NOTIFY_ON_NO_CHANGES` | Send notifications even when no changes occurred | false | No |
| `NOTIFY_ON_ERRORS_ONLY` | Only send notifications when errors occur | false | No |
| `BATCH_SIZE` | Number of movies per batch in Claude API calls | 150 | No |

### Kometa Configuration

Kometa-AI looks for collection definitions in YAML files located in the `/app/kometa-config` directory. These files should follow the standard Kometa format with special comment blocks for AI configuration.

Example collection configuration:

```yaml
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
    radarr_taglist: KAI-film-noir
```

See the `config-examples` directory for more sample collection configurations.

## Volume Management

Kometa-AI uses three Docker volumes that should be persisted:

1. `/app/kometa-config`: Contains Kometa collection definition files
2. `/app/state`: Contains the state file that tracks AI decisions
3. `/app/logs`: Contains application logs

Important considerations:

- Ensure these volumes are mapped to persistent storage on the host
- Back up the state directory regularly to prevent loss of AI decisions
- Consider log rotation for the logs directory to prevent excessive disk usage
- Ensure the volumes have appropriate permissions (readable/writable by the container)

Example volume setup with appropriate permissions:

```bash
mkdir -p kometa-ai/{kometa-config,state,logs}
chmod 755 kometa-ai/kometa-config
chmod 777 kometa-ai/state kometa-ai/logs
```

## Security Considerations

### API Keys

- Store API keys securely using environment variables, not in files
- Use a Radarr API key with minimal permissions (read/write tags only if possible)
- Consider using Docker secrets for sensitive information in production environments

### Network Security

- Avoid exposing Kometa-AI directly to the internet
- Use internal Docker networks for communication with Radarr
- If using remote services, ensure network traffic is encrypted (HTTPS)

### Container Security

- The Docker image runs as a non-root user for improved security
- Keep Docker and the Kometa-AI image updated regularly
- Consider enabling Docker's security features like read-only filesystems for additional security

## Monitoring and Logging

### Log Files

Logs are written to the `/app/logs` directory. The log level is controlled by the `DEBUG_LOGGING` environment variable.

To view logs from the running container:

```bash
docker logs kometa-ai
```

Or to view logs directly from the logs volume:

```bash
tail -f kometa-ai/logs/kometa_ai.log
```

### Health Check

Kometa-AI includes a built-in health check that verifies connectivity to Radarr and Claude APIs. You can manually run this check:

```bash
docker exec kometa-ai python -m kometa_ai --health-check
```

The Docker container also includes a configured healthcheck that runs automatically.

### Monitoring Options

- Use Docker's built-in health check status for basic monitoring
- Integrate with container monitoring solutions like Prometheus/Grafana
- Set up email notifications for errors using the built-in notification system
- Monitor disk usage of the persistent volumes

## Backup and Restore

### What to Back Up

1. State directory: Contains all AI decisions and processing history
2. Kometa configuration files: Contains your collection definitions
3. Docker Compose file or run command for easy redeployment

### Backup Process

Simple backup script example:

```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups/kometa-ai"
DATE=$(date +%Y-%m-%d)
mkdir -p "$BACKUP_DIR/$DATE"

# Backup state and configuration
cp -r kometa-ai/state "$BACKUP_DIR/$DATE/"
cp -r kometa-ai/kometa-config "$BACKUP_DIR/$DATE/"
cp docker-compose.yml "$BACKUP_DIR/$DATE/"

# Compress
tar -czf "$BACKUP_DIR/kometa-ai-backup-$DATE.tar.gz" -C "$BACKUP_DIR/$DATE" .
rm -rf "$BACKUP_DIR/$DATE"

# Keep only the 7 most recent backups
ls -tp "$BACKUP_DIR" | grep -v '/$' | tail -n +8 | xargs -I {} rm -- "$BACKUP_DIR/{}"
```

### Restore Process

To restore from a backup:

1. Stop the Kometa-AI container:
   ```bash
   docker-compose down
   ```

2. Extract the backup:
   ```bash
   tar -xzf kometa-ai-backup-YYYY-MM-DD.tar.gz -C /tmp/restore
   ```

3. Copy the files to your Kometa-AI directory:
   ```bash
   cp -r /tmp/restore/state/* kometa-ai/state/
   cp -r /tmp/restore/kometa-config/* kometa-ai/kometa-config/
   ```

4. Restart the container:
   ```bash
   docker-compose up -d
   ```

## Upgrading

### Standard Upgrade Process

1. Pull the latest image:
   ```bash
   docker pull kometa-ai:latest
   ```

2. Restart the container:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Major Version Upgrades

For major version upgrades:

1. Back up your data following the backup process above
2. Check the release notes for any breaking changes
3. Update your Docker Compose file if needed
4. Pull the new image and restart
5. Check logs for any migration or initialization messages

## Troubleshooting

### Common Issues

#### Container Won't Start

Check logs for error messages:
```bash
docker logs kometa-ai
```

Verify environment variables and volume mounts:
```bash
docker inspect kometa-ai
```

#### API Connection Errors

Verify connectivity to Radarr:
```bash
docker exec kometa-ai curl -s -I http://radarr:7878/api/v3/system/status
```

Check API keys:
```bash
docker exec kometa-ai python -m kometa_ai --health-check
```

#### High Resource Usage

For libraries with over 5,000 movies, adjust batch size:
```bash
docker-compose down
# Update BATCH_SIZE in your docker-compose.yml
docker-compose up -d
```

#### Other Issues

Reset state (use with caution, will clear all AI decisions):
```bash
docker exec kometa-ai python -m kometa_ai --reset-state
```

Test specific collection processing:
```bash
docker exec kometa-ai python -m kometa_ai --run-now --collection "Film Noir" --dry-run
```

## Performance Tuning

### Optimizing for Library Size

| Library Size | Recommended Batch Size | RAM Allocation |
|--------------|------------------------|---------------|
| < 1,000 movies | 150-200 | 1 GB |
| 1,000-5,000 movies | 100-150 | 2 GB |
| 5,000-10,000 movies | 75-100 | 4 GB |
| > 10,000 movies | 50-75 | 8 GB |

### Optimizing Schedule

- For large libraries, run less frequently (weekly instead of daily)
- Schedule runs during off-peak hours
- Consider processing collections in batches (process different collections on different days)

### Batch Size Optimization

Kometa-AI includes a batch size optimization tool to determine the optimal settings for your specific environment:

```bash
docker exec kometa-ai python -m kometa_ai --optimize-batch-size
```

## Integration with Kometa

### Tag Naming Convention

Kometa-AI manages tags with the prefix `KAI-` (e.g., `KAI-film-noir`).

### Kometa Collection Setup

In your Kometa configuration, set up a collection that uses the AI-managed tags:

```yaml
collections:
  Film Noir:
    radarr_tag: KAI-film-noir
    summary: Classic film noir movies from the 1940s and 1950s
    sort_title: +100_Film_Noir
```

### Workflow

1. Kometa-AI evaluates movies and applies tags in Radarr
2. Kometa reads these tags to create collections in Plex
3. Changes propagate from Radarr to Plex via Kometa

### Testing the Integration

1. Run Kometa-AI with a single collection:
   ```bash
   docker exec kometa-ai python -m kometa_ai --run-now --collection "Film Noir"
   ```

2. Verify tags in Radarr
3. Run Kometa to update Plex collections
4. Verify the collection appears in Plex