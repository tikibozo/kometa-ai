# Radarr Testing Environment

This document describes how to use the Radarr testing environment for validating Stage 2 changes in the Kometa-AI project.

## Overview

The Stage 2 changes focus on Radarr integration with tag management capabilities. This testing environment includes:

1. A real Radarr container (using the linuxserver/radarr image)
2. The Kometa-AI application configured to connect to this Radarr instance
3. Sample movies for testing tag management functionality

## Usage

A single script `radarr_test.sh` provides all necessary functionality for testing:

```bash
./radarr_test.sh [command]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `start` | Start the Radarr test environment |
| `setup` | Set up Radarr with root folder and sample movies |
| `test` | Run tests against Radarr |
| `validate` | Run the full validation process |
| `stop` | Stop the Radarr test environment |

### Complete Validation Workflow

To run the complete validation workflow:

```bash
./radarr_test.sh validate
```

This will:
1. Start the Radarr container
2. Set up the Radarr configuration
3. Add sample movies
4. Run the tests
5. Start the Kometa-AI application against Radarr

### Manual Steps

If you prefer to run steps individually:

1. **Start the environment**:
   ```bash
   ./radarr_test.sh start
   ```

2. **Set up Radarr**:
   - Complete the setup wizard at http://localhost:7878
   - Set the API Key to `0123456789abcdef0123456789abcdef` in Settings > General

3. **Add test data**:
   ```bash
   ./radarr_test.sh setup
   ```

4. **Run tests**:
   ```bash
   ./radarr_test.sh test
   ```

5. **Stop the environment**:
   ```bash
   ./radarr_test.sh stop
   ```

## Test Data

The test environment automatically adds 10 sample movies covering different genres:

- Action: Inception, The Dark Knight
- Drama: Forrest Gump, Fight Club
- Comedy: The Hangover
- Sci-Fi: The Matrix, Blade Runner 2049
- Thriller: Pulp Fiction, Se7en

## Configuration

The test environment uses the following configuration:

- Radarr URL: `http://localhost:7878`
- API Key: `0123456789abcdef0123456789abcdef`
- Root folder: `/movies`
- Quality profile ID: 1

## Troubleshooting

### API Key Issues

If you're having issues with the API key:
1. Open Radarr at http://localhost:7878
2. Go to Settings > General
3. Set the API Key to `0123456789abcdef0123456789abcdef`
4. Save the settings

### Docker Issues

If containers won't start:
```bash
docker-compose -f docker-compose.test.yml down
docker-compose -f docker-compose.test.yml up -d radarr
```

### View Logs

To see Radarr logs:
```bash
docker-compose -f docker-compose.test.yml logs -f radarr
```

To see Kometa-AI logs:
```bash
docker-compose -f docker-compose.test.yml logs -f kometa-ai
```