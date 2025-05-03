# CI/CD for Kometa-AI

This document describes the CI/CD (Continuous Integration/Continuous Delivery) approach for the Kometa-AI project.

## Overview

The CI/CD pipeline for Kometa-AI is built to ensure code quality and reliable deployments. The pipeline includes:

- Testing on Python 3.11
- Linting and type checking
- Code coverage analysis
- Docker image building and publishing

## Key Scripts

The following scripts are used in the CI/CD process:

### `ci_setup.py`

A consolidated script that handles CI environment setup:

```bash
# Run all setup tasks
python ci_setup.py

# Run only state module fixes
python ci_setup.py --state-module

# Run only test data creation
python ci_setup.py --test-data

# Enable verbose logging
python ci_setup.py --verbose
```

This script replaces the following obsolete scripts that have been removed:
- `ci_ensure_test_data.py`
- `ci_fix_state_module.py`
- `run_ci_fix.py`
- `scripts/run_ci_tests.sh`
- `dynamic_fix.py`
- `run_tests.sh`

### `run_tests.py`

A comprehensive test runner that can be used locally or in CI:

```bash
# Run all tests
python run_tests.py

# Run setup only
python run_tests.py --setup

# Run unit tests only
python run_tests.py --unit

# Run integration tests only
python run_tests.py --integration

# Run a specific test module
python run_tests.py --module test_parser

# Generate coverage report
python run_tests.py --coverage

# Skip setup steps
python run_tests.py --no-setup

# Run in CI mode (skips production tests)
python run_tests.py --ci
```

## GitHub Actions Workflow

The CI/CD pipeline is implemented using GitHub Actions in the `.github/workflows/kometa-ci-cd.yml` file.

### Jobs

1. **test**: Runs the complete test suite.
2. **lint-and-type-check**: Performs linting with flake8 and type checking with mypy.
3. **coverage**: Generates and uploads coverage reports.
4. **build-and-push**: Builds and publishes Docker images for main branch commits and tags.

## Local Development

For local development and testing:

1. Set up the environment:
   ```bash
   python ci_setup.py
   ```

2. Run tests:
   ```bash
   python run_tests.py
   ```

3. Generate coverage reports:
   ```bash
   python run_tests.py --coverage
   ```

## Troubleshooting

### State Module Import Issues

If you encounter import errors with the `kometa_ai.state` module:

```bash
python ci_setup.py --state-module
```

This will:
- Fix the state module structure
- Ensure all `py.typed` files exist
- Copy necessary files to site-packages
- Verify imports are working

### Missing Test Data

If test data is missing:

```bash
python ci_setup.py --test-data
```

This will create sample movie and collection data in the `test_data` directory.

## Docker Image

The Docker image is built and published automatically when:
- Code is pushed to the main branch
- A new tag is created (prefixed with 'v')

The image includes all necessary dependencies and the Kometa-AI application.