# Development Guide for Kometa-AI

This guide provides comprehensive instructions for setting up, developing, and testing Kometa-AI in different environments.

## Setting Up Development Environment

### Option 1: Local Python Virtual Environment

1. Make sure you have Python 3.8+ installed
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   pip install -e .  # Install package in development mode
   ```
4. Configure environment variables (required for running):
   ```bash
   export RADARR_URL="http://localhost:7878"
   export RADARR_API_KEY="your_api_key"
   export CLAUDE_API_KEY="your_api_key"
   # Optional variables
   export SMTP_SERVER="smtp.example.com"
   export SMTP_PORT="587"
   export NOTIFICATION_RECIPIENTS="user@example.com"
   ```

### Option 2: Using Docker

1. Make sure Docker and Docker Compose are installed and running
2. Use the provided Docker development script:
   ```bash
   ./docker_dev.sh
   ```
   Or use Docker Compose directly:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. The Docker setup automatically:
   - Builds the development Docker image
   - Sets up volumes for configuration, state, and logs
   - Configures environment variables from `.env` file (create this from the example below)

Example `.env` file for Docker:
```
RADARR_URL=http://radarr:7878
RADARR_API_KEY=your_api_key
CLAUDE_API_KEY=your_api_key
DEBUG_LOGGING=true
SCHEDULE_INTERVAL=1d
SCHEDULE_START_TIME=03:00
# Email notification settings (optional)
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_password
SMTP_USE_TLS=true
NOTIFICATION_RECIPIENTS=user@example.com
```

## Running Kometa-AI

### Using Helper Scripts

The simplest way to run Kometa-AI is using the helper scripts:

1. For local development with auto-setup:
   ```bash
   ./run_local.sh --run-now --dry-run
   ```

2. For Docker development:
   ```bash
   ./docker_dev.sh
   ```

### Manual Execution

If you prefer to run the commands manually:

1. With an activated virtual environment:
   ```bash
   # Run once immediately in dry-run mode
   python -m kometa_ai --run-now --dry-run
   
   # Run once for a specific collection
   python -m kometa_ai --collection "Science Fiction" --run-now
   
   # Run in scheduled mode (automatic recurring execution)
   python -m kometa_ai
   ```

2. Inside Docker container:
   ```bash
   docker exec -it kometa-ai python -m kometa_ai --run-now
   ```

## Testing Framework

Kometa-AI uses pytest for testing. The project includes unit tests, integration tests, and end-to-end tests.

### Running Tests

#### Using Helper Script

The easiest way to run tests is using the helper script:

```bash
# Run all tests
./run_tests.sh

# Run specific test file
./run_tests.sh tests/test_config.py

# Run specific test class
./run_tests.sh tests/test_config.py::TestConfig

# Run specific test method
./run_tests.sh tests/test_config.py::TestConfig::test_get_bool
```

#### Running Pytest Directly

If you're in an activated virtual environment:

```bash
# Run all tests
python -m pytest

# Run all tests with verbose output
python -m pytest -v

# Run specific test module
python -m pytest tests/test_config.py

# Run a specific test class
python -m pytest tests/test_config.py::TestConfig

# Run a specific test method
python -m pytest tests/test_config.py::TestConfig::test_get_bool
```

### Test Coverage

Measure test coverage with pytest-cov:

```bash
# Basic coverage report
./run_tests.sh --cov=kometa_ai

# Detailed coverage report
./run_tests.sh --cov=kometa_ai --cov-report=term-missing

# Generate HTML coverage report
./run_tests.sh --cov=kometa_ai --cov-report=html
# Then open htmlcov/index.html in a browser
```

### Test Types

1. **Unit Tests**: Test individual components in isolation
   ```bash
   # Examples
   python -m pytest tests/test_config.py
   python -m pytest tests/test_state_manager.py
   ```

2. **Integration Tests**: Test interaction between components
   ```bash
   # Examples
   python -m pytest tests/test_claude_integration.py
   python -m pytest tests/test_radarr_tag_manager.py
   ```

3. **End-to-End Tests**: Test full application workflow
   ```bash
   python -m pytest tests/test_pipeline.py
   ```

4. **Component-Specific Tests**:
   ```bash
   # Email notification system
   python -m pytest tests/test_email_notification.py
   
   # Scheduling system
   python -m pytest tests/test_scheduling.py
   
   # Kometa configuration parser
   python -m pytest tests/test_kometa_parser.py
   ```

## Running in Test Environments

### Radarr Test Environment

For testing with a real Radarr instance:

1. Start the test Radarr environment:
   ```bash
   ./run_test_env.sh
   ```

2. Run automated Radarr tests:
   ```bash
   ./radarr_test.sh
   ```

3. Add test movies to Radarr:
   ```bash
   python add_test_movies.py
   ```

### Docker Test Environment

Run the application with the test Docker configuration:

```bash
docker-compose -f docker-compose.test.yml up -d
```

## Common Commands and Operations

### Runtime Options

```bash
# Run with specific collection
./run_local.sh --collection "Film Noir" --run-now --dry-run

# Run health check to verify API connections
./run_local.sh --health-check

# View current configuration
./run_local.sh --dump-config

# Reset state (clear all stored decisions)
./run_local.sh --reset-state

# Run with debug logging
DEBUG_LOGGING=true ./run_local.sh --run-now
```

### Scheduling Options

```bash
# Run with custom schedule (every 12 hours starting at 6:00)
SCHEDULE_INTERVAL=12h SCHEDULE_START_TIME=06:00 ./run_local.sh
```

### Email Notification Testing

```bash
# Test email configuration
SMTP_SERVER=smtp.example.com \
SMTP_PORT=587 \
SMTP_USERNAME=your_username \
SMTP_PASSWORD=your_password \
SMTP_USE_TLS=true \
NOTIFICATION_RECIPIENTS=user@example.com \
./run_local.sh --health-check
```

## Performance Testing and Optimization

Kometa-AI includes comprehensive tools for performance testing, profiling, and optimization, particularly for large movie libraries.

### Running Performance Tests

#### Using Command-line Options

The main application includes built-in performance profiling options:

```bash
# Enable performance profiling for a run
./run_local.sh --run-now --profile

# Save profiling results to a specific file
./run_local.sh --run-now --profile --profile-output my_profile_results.json

# Run with more detailed memory profiling
./run_local.sh --run-now --memory-profile

# Run batch size optimization test
./run_local.sh --optimize-batch-size
```

#### Using Test Scripts

For more detailed performance testing with synthetic data:

1. Generate test data:
   ```bash
   # Generate a small dataset (50 movies)
   python generate_test_data.py -n 50 -o test_data/small_test.json

   # Generate a medium dataset (1000 movies)
   python generate_test_data.py -n 1000 -o test_data/medium_test.json

   # Generate a large dataset (10000 movies)
   python generate_test_data.py -n 10000 -o test_data/large_test.json
   ```

2. Run performance tests:
   ```bash
   # Test with small dataset
   python test_large_dataset.py -f test_data/small_test.json -b 150

   # Test memory optimization
   python test_optimization.py test_data/medium_test.json

   # Test with batch size optimization
   python test_large_dataset.py -f test_data/medium_test.json --optimize-batch-size
   ```

### Understanding Profiling Results

Performance profiling results are saved as JSON files with the following structure:

```json
{
  "timing": {
    "total_duration": 120.5,
    "collection_durations": {...}
  },
  "memory": {
    "peak": {"rss_peak": 256000000, "vms_peak": 512000000},
    "current": {...},
    "diff": {...},
    "top_allocations": [...]
  },
  "api_calls": {
    "claude/messages": {
      "count": 10,
      "input_tokens": 80000,
      "output_tokens": 5000
    }
  },
  "batch_efficiency": {
    "150": {
      "count": 8,
      "total_items": 1200,
      "efficiency": 0.97
    }
  },
  "collections": {
    "Film Noir": {
      "duration": 45.2,
      "movies_processed": 453,
      "from_cache": 547,
      "tokens": {
        "input": 45300,
        "output": 2200
      }
    }
  }
}
```

Key metrics to look for:
- **Memory peak**: The maximum memory usage during processing
- **Total duration**: Overall processing time
- **Tokens used**: API token usage (affects cost)
- **Efficiency**: How efficiently batches are utilized

### Optimizing for Large Libraries

For best performance with large movie libraries (5,000+ movies):

1. First run with batch size optimization to determine the optimal batch size:
   ```bash
   ./run_local.sh --optimize-batch-size
   ```

2. Take note of the recommended batch size in the output, then run with this size:
   ```bash
   ./run_local.sh --run-now --batch-size <optimal_size> --profile
   ```

3. Review the profiling results to identify bottlenecks:
   ```bash
   cat profile_results.json
   ```

4. Consider these optimization options:
   - Decrease collection count if processing too many collections
   - Fine-tune batch size based on your system's memory constraints
   - Adjust scheduling for less frequent but more optimized runs

## Development Best Practices

1. **Write Tests First**: Add tests for new features before implementing them
2. **Check Coverage**: Aim to maintain or improve the test coverage percentage
3. **Use Dry Run**: Always test changes with `--dry-run` before applying them to your Radarr library
4. **Debug Logging**: Enable debug logging with `DEBUG_LOGGING=true` to see detailed operation
5. **Profile Performance**: Use profiling tools to identify and fix bottlenecks for large libraries

## Troubleshooting

- **Test Failures**: Check the test logs and ensure environment variables are correctly set
- **Docker Issues**: Ensure volumes are properly mounted and check container logs
- **API Connection Problems**: Verify your API keys and connection URLs
- **Email Notifications**: Check SMTP settings and try connecting to the server manually
- **Performance Issues**:
  - **High Memory Usage**: Try reducing batch size (--batch-size), run with --memory-profile to diagnose
  - **Slow Processing**: Check collection count, run --optimize-batch-size to find optimal settings
  - **API Failures**: Check for token limits, increase retries in code, implement backoff strategy
  - **Out of Memory Errors**: Ensure your system has enough RAM, reduce collection count, or process collections sequentially

## Support and Contributions

For questions, issues, or contributions:
1. Check the project documentation
2. Look for similar issues in the issue tracker
3. Open a new issue with detailed information about your problem or suggestion