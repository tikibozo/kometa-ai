# CI/CD for Kometa-AI

This document describes the CI/CD (Continuous Integration/Continuous Delivery) approach for the Kometa-AI project.

## Overview

The CI/CD pipeline for Kometa-AI is built to ensure code quality and reliable deployments. The pipeline includes:

- Testing on Python 3.11
- Linting
- Code coverage reporting
- Docker image building and publishing

## GitHub Actions Workflow

The CI/CD pipeline is implemented using GitHub Actions in the `.github/workflows/kometa-ci-cd.yml` file.

### Jobs

1. **test**: Installs the package with `pip install -e .`, runs the test suite with `python -m pytest`, and uploads the coverage report to Codecov.
2. **lint**: Performs linting with flake8.
3. **build-and-push**: Builds and publishes Docker images for main branch commits and tags.

## Local Development

For local development and testing:

1. Set up the environment:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   pip install -e .
   ```

2. Run tests (coverage is generated automatically via `pytest.ini`):
   ```bash
   python -m pytest
   ```

3. Run a specific test module:
   ```bash
   python -m pytest tests/test_parser.py
   ```

Static test fixtures used by the tests live in `test_data/` (`synthetic_movies.json`, `synthetic_collections.json`) and are committed to the repository.

## Docker Image

The Docker image is built and published automatically when:
- Code is pushed to the main branch
- A new tag is created (prefixed with 'v')

The image includes all necessary dependencies and the Kometa-AI application.
