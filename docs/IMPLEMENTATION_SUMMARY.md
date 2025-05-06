# Improved Collection Confidence Accuracy Implementation

## Summary

We have successfully implemented the Phase 1 improvements to enhance the collection confidence accuracy by providing better context to Claude. These changes will help Claude make better decisions when evaluating movie suitability for collections, addressing issues like the "Inception in Heist Movies" problem.

## Changes Implemented

### 1. Enhanced System Prompt

We updated the system prompt in `kometa_ai/claude/prompts.py` to:
- Focus on primary themes rather than incidental elements
- Explicitly warn against including movies based on minor genre elements
- Provide concrete examples of common misclassifications
- Guide Claude to evaluate movie content beyond just what's mentioned in the overview

```python
# Key improvements in system prompt
"""
- Evaluate the movie's actual content and themes, not just what's mentioned in the overview
- Be cautious about superficial similarities and lookout for mismatches between overview and actual film content
- Be discriminating: a movie containing elements of a genre doesn't necessarily mean it belongs in that collection
- Consider the movie's primary themes and genres, not incidental elements

IMPORTANT: For collections based on themes or genres, focus on whether the movie is primarily about that theme/genre, not whether it contains elements of it. For example:
- A movie with one heist scene is not necessarily a "Heist Movie"
- A movie set partly in space is not necessarily a "Space Movie" 
- A movie with some comedy is not necessarily a "Comedy Movie"
"""
```

### 2. Improved Collection Prompt

We enhanced the collection-specific prompts to:
- Include important considerations for each collection
- Remind Claude to focus on primary themes and content
- Consider typical viewer categorization
- Supplement limited data with Claude's knowledge of cinema

```python
# Key additions to collection prompt
"""
IMPORTANT CONSIDERATIONS FOR THIS COLLECTION:
- You should only include movies that strongly match the collection's theme/genre
- A movie that contains minor elements or scenes related to the collection theme should NOT be included
- Focus on the movie's primary themes and content, not secondary elements
- When evaluating movies, use your knowledge of cinema to supplement the data provided
- Consider whether a typical viewer would categorize this movie primarily as a {collection.name.rstrip('s')} film
"""
```

### 3. Iterative Refinement for Borderline Cases

We implemented a two-pass approach for borderline cases:
- Added `use_iterative_refinement` and `refinement_threshold` to `CollectionConfig`
- Created methods to identify borderline cases (near the confidence threshold)
- Added detailed analysis prompts for deeper evaluation of these cases
- Implemented storage of detailed analysis for future reference

```yaml
# Example configuration with iterative refinement enabled
# === KOMETA-AI ===
# enabled: true
# use_iterative_refinement: true
# refinement_threshold: 0.15
# confidence_threshold: 0.7
# prompt: |
#   Identify heist movies based on these criteria:
#   - Central plot revolves around planning and executing a heist or robbery
#   ...
# === END KOMETA-AI ===
```

### 4. State Management for Detailed Analysis

We enhanced the state management system to:
- Store detailed analyses for borderline cases
- Persist these analyses between runs
- Allow retrieval of analyses for review or debugging

## Testing

All tests for our implementation are passing, including:
- Tests for the updated parsers
- Tests for state management functionality
- Tests for detailed analysis storage and retrieval
- Tests for the iterative refinement process

## Next Steps

These Phase 1 improvements should significantly improve collection accuracy by addressing the core issues:

1. Claude now focuses on primary themes rather than incidental elements
2. Borderline cases receive a more detailed second-pass analysis
3. The system makes better use of Claude's broader knowledge of cinema

For further improvements (in future phases), we would recommend:
1. Integrating with TMDB's extended data API for richer movie context
2. Pre-computing deeper movie analyses when movies are added
3. Implementing user feedback mechanisms

## Using the New Features

To enable iterative refinement for a collection, add these parameters to the collection configuration:

```yaml
# === KOMETA-AI ===
# enabled: true
# use_iterative_refinement: true  # Enable iterative refinement
# refinement_threshold: 0.15      # Analyze movies with confidence within 0.15 of threshold
# confidence_threshold: 0.7
# prompt: |
#   ...
# === END KOMETA-AI ===
```

When this is enabled, movies with confidence scores near the threshold will receive a more thorough analysis, helping to prevent misclassifications like the Inception case.