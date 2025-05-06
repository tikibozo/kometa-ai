# StateManager Implementation Guide

This document explains the architecture, implementation, and management of the `StateManager` class within the Kometa-AI project.

## Overview

The `StateManager` class is responsible for persistent state management in the Kometa-AI system. It handles:

- Loading and saving state from disk
- Tracking movie collection decisions
- Logging changes and errors
- Providing access to historical data

## Implementation Approach

The `StateManager` class exists in multiple places within the codebase, which requires careful coordination:

1. **Primary Implementation**: `kometa_ai/state/manager.py`
2. **Mock Implementation**: `tests/conftest.py` (in `MockStateManager` class)
3. **Build-time Generated**: Created by `scripts/pre_build_setup.sh` during build
4. **CI-Generated**: Created by `ci_setup.py` during CI runs

To ensure consistency across these implementations, we use the following approach:

### Single Source of Truth

The primary implementation in `kometa_ai/state/manager.py` is considered the canonical version. All other implementations should follow its interface and behavior.

A template version is provided in `templates/state_manager_template.py` which can be used as a reference for hardcoded implementations in scripts.

### Required Methods

The following methods must be implemented in all versions of `StateManager`:

- `load()`: Load state from disk
- `save()`: Save state to disk
- `reset()`: Reset state to empty
- `get_decision(movie_id, collection_name)`: Get a decision for a movie/collection pair
- `set_decision(decision)`: Set a decision for a movie/collection pair
- `get_decisions_for_movie(movie_id)`: Get all decisions for a movie
- `get_metadata_hash(movie_id)`: Get the stored metadata hash for a movie
- `log_change(movie_id, movie_title, collection_name, action, tag)`: Log a tag change
- `log_error(context, error_message)`: Log an error
- `get_changes()`: Get recent changes
- `get_errors()`: Get recent errors
- `clear_errors()`: Clear all error records
- `clear_changes()`: Clear all change records
- `dump()`: Dump state as formatted JSON string

### Verification

To ensure consistent implementations, we use:

1. **Automated Tests**: `tests/test_state_implementations.py` verifies that both implementations have the required methods with correct signatures
2. **CI Verification**: `scripts/verify_state_module.py` runs during CI to check that the implementations have all required methods
3. **Runtime Fallbacks**: Code in `conftest.py` ensures that methods are always available at runtime by adding them dynamically if needed

## Modifying StateManager

When adding or changing methods in the `StateManager` class, follow these steps:

1. **Update Primary Implementation**: First modify `kometa_ai/state/manager.py`
2. **Update Mock Implementation**: Update `MockStateManager` in `tests/conftest.py`
3. **Update Template**: Update `templates/state_manager_template.py`
4. **Update Required Methods**: If adding a new method, add it to:
   - `REQUIRED_METHODS` in `tests/test_state_implementations.py`
   - `REQUIRED_METHODS` in `scripts/verify_state_module.py`
5. **Update CI script**: If necessary, update the hardcoded implementation in `scripts/pre_build_setup.sh`
6. **Run Tests**: Verify that `pytest tests/test_state_implementations.py` passes

## Best Practices

- Keep methods synchronized across all implementations
- Use proper type hints and docstrings in all implementations
- Add new methods to the verification scripts immediately
- Add tests for new functionality
- Ensure mock implementations have reasonable behavior for tests

## Common Issues

- **CI Failures**: If the CI fails with `AttributeError` related to StateManager, check that all implementations have the required methods
- **Import Errors**: Ensure the file structure is consistent and tests can find the implementations
- **Signature Mismatches**: Verify that method signatures match across implementations
- **Runtime Failures**: Check for edge cases in mock implementations that tests might rely on

## Related Files

- `/kometa_ai/state/manager.py`: Primary implementation
- `/kometa_ai/state/models.py`: Models used by StateManager
- `/templates/state_manager_template.py`: Template for implementations
- `/tests/conftest.py`: Contains MockStateManager
- `/scripts/verify_state_module.py`: Verification script for CI
- `/scripts/pre_build_setup.sh`: Build script that creates state files
- `/tests/test_state_implementations.py`: Tests for implementation consistency