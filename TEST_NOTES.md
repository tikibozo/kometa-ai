# Kometa-AI Testing Notes

This document provides information about the Kometa-AI test suite and how to run tests in different environments.

## Test Suite Overview

The Kometa-AI test suite includes several types of tests:
- Unit tests
- Integration tests
- Production deployment tests

The production deployment tests require Docker and test the actual deployment of the application in containers. These tests are resource-intensive and may take some time to run, so they're skipped by default in local development and CI environments.

## Running Tests

### Basic Test Commands

```bash
# Run all tests (except production deployment tests)
./run_tests.sh

# Include production deployment tests
./run_tests.sh --include-production

# Run specific test files
./run_tests.sh tests/test_config.py tests/test_state_manager.py

# Force reinstall dependencies
./run_tests.sh --force-install
```

### CI Environment Tests

For CI environments, use the `run_ci_tests.sh` script, which sets the appropriate environment variables and skips production deployment tests:

```bash
# Run CI tests
./scripts/run_ci_tests.sh
```

### Test Categories

- **Basic Functionality Tests**: Test the core functionality of Kometa-AI
  ```bash
  ./run_tests.sh tests/test_config.py tests/test_state_manager.py tests/test_kometa_parser.py
  ```

- **Radarr Integration Tests**: Test interaction with the Radarr API
  ```bash
  ./run_tests.sh tests/test_radarr_tag_manager.py tests/test_tag_manager.py
  ```

- **Claude Integration Tests**: Test interaction with the Claude AI API
  ```bash
  ./run_tests.sh tests/test_claude_integration.py tests/test_claude_processor.py
  ```

- **Pipeline Tests**: Test the full pipeline from data collection to tag application
  ```bash
  ./run_tests.sh tests/test_pipeline.py
  ```

- **Production Tests**: Test Docker deployment (requires Docker)
  ```bash
  ./run_tests.sh --include-production tests/test_production_deployment.py
  ```

## Production Deployment Tests

The production deployment tests check that the Docker containers are properly configured and running. These tests:

1. Build and run Docker containers
2. Verify container health checks
3. Test environment variable processing
4. Verify volumes are correctly mounted
5. Check security best practices

To run these tests, Docker must be installed and running on your machine. You can run them with:

```bash
./run_tests.sh --include-production tests/test_production_deployment.py
```

Note that these tests may take some time to run and use significant system resources.

## Test Coverage

The test suite generates coverage reports in both terminal output and XML format for CI tools. You can generate HTML coverage reports with:

```bash
coverage html
```

Then open `htmlcov/index.html` in your browser to view detailed coverage information.

## Troubleshooting Tests

If you encounter issues with the tests:

1. Make sure dependencies are installed:
   ```bash
   ./run_tests.sh --force-install
   ```

2. Check if you have the right Python version (3.8+):
   ```bash
   python --version
   ```

3. For Docker-related test failures, verify Docker is running:
   ```bash
   docker info
   ```

4. If specific tests are failing, try running just those tests with verbose output:
   ```bash
   ./run_tests.sh -v tests/test_specific_module.py
   ```

5. Check log files for more detailed error information:
   ```bash
   tail -f logs/kometa_ai.log
   ```