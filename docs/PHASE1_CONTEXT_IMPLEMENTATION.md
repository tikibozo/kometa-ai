# Phase 1: Immediate Improvements Implementation Guide

This document outlines the implementation details for the first phase of improvements to increase collection confidence accuracy by providing better context to Claude.

## 1. Enhanced Prompt Engineering

### Updated System Prompt

```python
def get_system_prompt() -> str:
    """Get the enhanced system prompt for Claude.

    Returns:
        System prompt
    """
    return """
You are a film expert tasked with categorizing movies for a Plex media server. Your job is to determine which movies belong in a specific collection based on the provided criteria.

Guidelines:
1. Focus ONLY on the specific collection definition and criteria provided
2. Consider all relevant movie attributes (title, year, genres, plot, directors, actors, etc.)
3. Apply the collection criteria consistently across all movies
4. Provide a confidence score (0.0-1.0) for each decision
5. Include reasoning ONLY for borderline cases (confidence between 0.4-0.8)
6. Return answers in valid JSON format only
7. Do not consider personal preferences or subjective quality judgments

When evaluating movies:
- Be objective and follow the criteria exactly
- Do not artificially limit the number of movies in a collection
- Include a movie if it fits the criteria, regardless of how many you've already included
- Exclude a movie if it doesn't fit the criteria, even if the collection would be empty
- For movies with little information, use your knowledge about films to supplement the data
- Evaluate the movie's actual content and themes, not just what's mentioned in the overview
- Be cautious about superficial similarities and lookout for mismatches between overview and actual film content
- Be discriminating: a movie containing elements of a genre doesn't necessarily mean it belongs in that collection
- Consider the movie's primary themes and genres, not incidental elements

IMPORTANT: For collections based on themes or genres, focus on whether the movie is primarily about that theme/genre, not whether it contains elements of it. For example:
- A movie with one heist scene is not necessarily a "Heist Movie"
- A movie set partly in space is not necessarily a "Space Movie" 
- A movie with some comedy is not necessarily a "Comedy Movie"

Your response must follow this exact JSON format:
{
  "collection_name": "Name of the collection",
  "decisions": [
    {
      "movie_id": 123,
      "title": "Movie Title",
      "include": true,
      "confidence": 0.95,
      "reasoning": "Optional explanation for borderline cases"
    },
    // Additional movies...
  ]
}

IMPORTANT: Return valid JSON only. Do not include markdown formatting or explanatory text outside the JSON structure.
"""
```

### Collection-Specific Prompt Enhancements

Update the `format_collection_prompt` function to include more guidance and examples:

```python
def format_collection_prompt(collection: CollectionConfig) -> str:
    """Format the prompt for a collection with additional guidance.

    Args:
        collection: Collection configuration

    Returns:
        Formatted prompt
    """
    # [Existing logging code]

    # Ensure the prompt is properly formatted
    formatted_prompt = collection.prompt.strip() if collection.prompt else ""
    
    # Add collection-specific example handling
    example_inclusions = collection.example_inclusions or []
    example_exclusions = collection.example_exclusions or []
    
    examples_section = ""
    if example_inclusions or example_exclusions:
        examples_section = "\nEXAMPLES TO GUIDE YOUR DECISIONS:\n"
        
        if example_inclusions:
            examples_section += "\nMovies that SHOULD be included in this collection:\n"
            for example in example_inclusions:
                examples_section += f"- {example['title']} ({example.get('year', '')}): {example.get('reason', '')}\n"
        
        if example_exclusions:
            examples_section += "\nMovies that should NOT be included in this collection:\n"
            for example in example_exclusions:
                examples_section += f"- {example['title']} ({example.get('year', '')}): {example.get('reason', '')}\n"
    
    # Create the formatted prompt template
    prompt_template = f"""
I need you to categorize movies for the "{collection.name}" collection.

COLLECTION DEFINITION AND CRITERIA:
{formatted_prompt}
{examples_section}

For each movie in the provided list, evaluate whether it belongs in the {collection.name} collection based on these criteria. Provide your decision and a confidence level (0.0-1.0) for each movie.

The minimum confidence threshold for inclusion is {collection.confidence_threshold}. For movies with confidence below this threshold, they will not be included in the collection, so be careful not to underestimate your confidence if you believe a movie should be included.

IMPORTANT CONSIDERATIONS FOR THIS COLLECTION:
- You should only include movies that strongly match the collection's theme/genre
- A movie that contains minor elements or scenes related to the collection theme should NOT be included
- Focus on the movie's primary themes and content, not secondary elements
- When evaluating movies, use your knowledge of cinema to supplement the data provided

Return your evaluation in the required JSON format ONLY, with no additional text or explanations outside the JSON structure.
"""

    # [Existing logging code]

    return prompt_template
```

## 2. Iterative Refinement for Borderline Cases

### Add Configuration Option

Update the `CollectionConfig` class to include the option for iterative refinement:

```python
@dataclass
class CollectionConfig:
    # Existing fields...
    use_iterative_refinement: bool = False
    refinement_threshold: float = 0.15  # Confidence margin for triggering refinement
```

### Implement Iterative Refinement in the Movie Processor

Add a method to handle iterative refinement for borderline cases:

```python
def _refine_borderline_cases(
    self,
    collection: CollectionConfig,
    decisions: List[Dict[str, Any]],
    batch_movies: List[Movie]
) -> List[Dict[str, Any]]:
    """Refine decisions for borderline cases with a second pass analysis.
    
    Args:
        collection: Collection configuration
        decisions: Initial decisions from Claude
        batch_movies: Movies in the current batch
        
    Returns:
        Refined decisions
    """
    if not collection.use_iterative_refinement:
        return decisions
        
    # Identify borderline cases
    borderline_cases = []
    movie_map = {movie.id: movie for movie in batch_movies}
    
    for decision in decisions:
        confidence = decision.get('confidence', 0.0)
        # Check if confidence is near the threshold
        if abs(confidence - collection.confidence_threshold) < collection.refinement_threshold:
            movie_id = decision.get('movie_id')
            if movie_id in movie_map:
                borderline_cases.append((decision, movie_map[movie_id]))
    
    # If no borderline cases, return original decisions
    if not borderline_cases:
        logger.info(f"No borderline cases found for collection '{collection.name}'")
        return decisions
        
    logger.info(f"Found {len(borderline_cases)} borderline cases for collection '{collection.name}'")
    
    # Create refined decisions
    refined_decisions = []
    for original_decision, movie in borderline_cases:
        try:
            # Create a detailed analysis prompt for this specific movie
            refinement_prompt = self._create_refinement_prompt(collection, movie)
            
            # Get detailed analysis from Claude
            detailed_response, _ = self.claude_client.analyze_movie(
                system_prompt=self._get_refinement_system_prompt(),
                user_prompt=refinement_prompt
            )
            
            # Extract the refined decision
            refined_decision = self._process_refinement_response(
                detailed_response, original_decision, collection
            )
            
            # Update the original decision with the refined one
            for i, decision in enumerate(decisions):
                if decision.get('movie_id') == movie.id:
                    decisions[i] = refined_decision
                    break
                
            logger.info(
                f"Refined decision for movie {movie.id} ({movie.title}): "
                f"Original confidence: {original_decision.get('confidence', 0.0):.2f}, "
                f"Refined confidence: {refined_decision.get('confidence', 0.0):.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error refining decision for movie {movie.id}: {e}")
            # Keep the original decision if refinement fails
    
    return decisions

def _create_refinement_prompt(self, collection: CollectionConfig, movie: Movie) -> str:
    """Create a detailed prompt for refining a borderline case.
    
    Args:
        collection: Collection configuration
        movie: The movie to analyze
        
    Returns:
        Detailed refinement prompt
    """
    return f"""
I need your help analyzing whether the movie "{movie.title}" ({movie.year}) should be included in the "{collection.name}" collection.

MOVIE DETAILS:
- Title: {movie.title}
- Year: {movie.year}
- Genres: {', '.join(movie.genres)}
- Overview: {movie.overview}

COLLECTION CRITERIA:
{collection.prompt}

This is a borderline case that needs deeper analysis. Please use your knowledge of films to thoroughly analyze this movie beyond the basic information provided. Consider:

1. The primary themes and focus of the movie
2. The genre conventions the movie follows
3. Whether the collection theme is central to the movie or just incidental
4. Similar movies that are definitively in or out of this collection
5. Critical reception and how the movie is categorized by experts

Based on your analysis, provide a detailed evaluation with a final confidence score and a clear yes/no decision.
"""

def _get_refinement_system_prompt(self) -> str:
    """Get the system prompt for detailed movie analysis.
    
    Returns:
        System prompt for refinement
    """
    return """
You are a film expert providing detailed analysis of whether a specific movie belongs in a themed collection.

For the movie and collection provided, conduct a thorough analysis using your knowledge of cinema.
Go beyond the basic information provided to analyze the movie's themes, style, reception, and how it fits with the collection criteria.

Return your analysis in this JSON format:
{
  "movie_title": "Title of the movie",
  "collection_name": "Name of the collection",
  "detailed_analysis": "Your in-depth analysis of why this movie does or doesn't belong",
  "include": true/false,
  "confidence": 0.95,
  "reasoning": "Concise explanation of your final decision"
}
"""

def _process_refinement_response(
    self, 
    response: Dict[str, Any], 
    original_decision: Dict[str, Any],
    collection: CollectionConfig
) -> Dict[str, Any]:
    """Process the refinement response from Claude.
    
    Args:
        response: Claude refinement response
        original_decision: Original decision
        collection: Collection configuration
        
    Returns:
        Updated decision
    """
    # Create a copy of the original decision
    refined_decision = original_decision.copy()
    
    # Update with refined information
    if 'include' in response:
        refined_decision['include'] = response['include']
    if 'confidence' in response:
        refined_decision['confidence'] = response['confidence']
    if 'reasoning' in response:
        refined_decision['reasoning'] = response['reasoning']
    
    # Include the detailed analysis in the state record but not in the decision
    # This will be saved for future reference but not sent back in the API response
    detailed_analysis = response.get('detailed_analysis', '')
    if detailed_analysis:
        # Store the detailed analysis in the state
        self.state_manager.set_detailed_analysis(
            movie_id=original_decision['movie_id'],
            collection_name=collection.name,
            analysis=detailed_analysis
        )
    
    return refined_decision
```

### Update the Client to Support Movie Analysis

Add a method to the `ClaudeClient` for detailed movie analysis:

```python
def analyze_movie(
    self,
    system_prompt: str,
    user_prompt: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Analyze a single movie in detail.
    
    Args:
        system_prompt: System prompt for the analysis
        user_prompt: User prompt with movie details
        
    Returns:
        Tuple of (analysis response, usage stats)
    """
    try:
        # Create message context
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ]
        
        # Make API request
        response = self.client.messages.create(
            model=self.model,
            messages=messages,
            max_tokens=2000,  # Adjust as needed
            temperature=0.1   # Lower temperature for more consistent results
        )
        
        # Extract response content
        content = response.content[0].text
        
        # Parse JSON from response
        try:
            analysis = json.loads(content)
        except json.JSONDecodeError:
            # Extract JSON from response using regex
            import re
            json_match = re.search(r'```json\n([\s\S]*?)\n```', content)
            if json_match:
                try:
                    analysis = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    analysis = {"error": "Failed to parse response JSON"}
            else:
                analysis = {"error": "Failed to parse response JSON"}
        
        # Calculate usage statistics
        usage_stats = {
            "total_input_tokens": response.usage.input_tokens,
            "total_output_tokens": response.usage.output_tokens,
            "total_cost": self._calculate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens
            ),
            "requests": 1
        }
        
        return analysis, usage_stats
        
    except Exception as e:
        logger.error(f"Error analyzing movie: {e}")
        raise
```

### Update State Manager to Store Detailed Analyses

Add the ability to store detailed analyses in the state:

```python
def set_detailed_analysis(
    self,
    movie_id: int,
    collection_name: str,
    analysis: str
) -> None:
    """Store detailed analysis for a movie and collection.
    
    Args:
        movie_id: Radarr movie ID
        collection_name: Collection name
        analysis: Detailed analysis text
    """
    key = f"movie:{movie_id}"
    collection_key = collection_name.lower()
    
    with self._state_lock:
        # Get existing movie data
        movie_data = self._state.get('decisions', {}).get(key, {})
        if not movie_data:
            movie_data = {'collections': {}}
            self._state.setdefault('decisions', {})[key] = movie_data
            
        # Get or create collection data
        collections = movie_data.get('collections', {})
        if collection_key not in collections:
            collections[collection_key] = {}
            
        # Add detailed analysis
        collections[collection_key]['detailed_analysis'] = analysis
        
        # Mark state as changed
        self._state_changed = True
```

### Integrate the Refinement Process in the Main Processing Loop

Update the `_process_decisions` method to include refinement:

```python
@retry_with_backoff(max_retries=3, base_delay=1.0)
def _process_decisions(
    self,
    response: Dict[str, Any],
    collection: CollectionConfig,
    batch_movies: List[Movie]
) -> Tuple[List[int], List[int]]:
    """Process decisions from Claude's response.

    Args:
        response: Claude API response
        collection: Collection configuration
        batch_movies: List of movies in this batch

    Returns:
        Tuple of (included movie IDs, excluded movie IDs)
    """
    try:
        if 'decisions' not in response:
            logger.error(f"Invalid response format: {response}")
            raise ValueError("Invalid response format: missing 'decisions' key")

        # Get initial decisions
        decisions = response['decisions']
        
        # Apply iterative refinement for borderline cases if enabled
        if collection.use_iterative_refinement:
            decisions = self._refine_borderline_cases(collection, decisions, batch_movies)
        
        included_ids = []
        excluded_ids = []
        movie_map = {movie.id: movie for movie in batch_movies}

        for decision_data in decisions:
            movie_id = decision_data.get('movie_id')

            if movie_id not in movie_map:
                logger.warning(f"Decision for unknown movie ID: {movie_id}")
                continue

            movie = movie_map[movie_id]
            include = decision_data.get('include', False)
            confidence = decision_data.get('confidence', 0.0)
            reasoning = decision_data.get('reasoning')

            # Create decision record
            decision = DecisionRecord(
                movie_id=movie_id,
                collection_name=collection.name,
                include=include,
                confidence=confidence,
                metadata_hash=movie.calculate_metadata_hash(),
                tag=collection.tag,
                timestamp=datetime.now(UTC).isoformat(),
                reasoning=reasoning
            )

            # Store decision
            self.state_manager.set_decision(decision)

            # Add to included/excluded lists based on threshold
            if include and confidence >= collection.confidence_threshold:
                included_ids.append(movie_id)
                logger.debug(
                    f"Including movie {movie_id} ({movie.title}) in collection '{collection.name}' "
                    f"with confidence {confidence:.2f}"
                )
            else:
                excluded_ids.append(movie_id)
                logger.debug(
                    f"Excluding movie {movie_id} ({movie.title}) from collection '{collection.name}' "
                    f"with confidence {confidence:.2f}"
                )

        # Checkpoint state after each batch to ensure we don't lose decisions
        self.state_manager.save()

        return included_ids, excluded_ids

    except Exception as e:
        # [Existing error handling code]
```

## Configuration Updates

To support these new features, we'll need to update our collection configuration format:

```yaml
collections:
  # === KOMETA-AI ===
  # enabled: true
  # prompt: |
  #   Identify heist movies based on these criteria:
  #   - Central plot revolves around planning and executing a heist or robbery
  #   - Features a team or individual assembling a plan to steal something valuable
  #   - Includes sequences showing planning, preparation, and execution of the heist
  #   - Often contains twists, double-crosses, or complications during the heist
  # confidence_threshold: 0.7
  # use_iterative_refinement: true
  # refinement_threshold: 0.15
  # example_inclusions:
  #   - title: "Ocean's Eleven"
  #     year: 2001
  #     reason: "Centered entirely around planning and executing a casino heist"
  #   - title: "The Italian Job"
  #     year: 2003
  #     reason: "Core plot is about a gold heist using Mini Coopers"
  # example_exclusions:
  #   - title: "Inception"
  #     year: 2010
  #     reason: "While it has elements of a heist (stealing ideas), it's primarily a sci-fi movie about dreams"
  #   - title: "The Dark Knight"
  #     year: 2008
  #     reason: "Opens with a bank robbery but is a superhero film, not a heist movie"
  # === END KOMETA-AI ===
  Heist Movies:
    radarr_taglist: KAI-heist-movies
    # ... existing Kometa config ...
```

## Implementation Plan

1. Update the `kometa/models.py` file to include the new configuration options
2. Enhance the system prompt in `claude/prompts.py`
3. Modify the collection prompt formatting in `claude/prompts.py`
4. Add the refinement functionality to the `claude/processor.py` file
5. Update the `claude/client.py` file with the new analysis method
6. Modify the state manager to store detailed analyses
7. Update the parser to handle the new configuration format

This implementation will provide immediate improvements to collection accuracy with minimal external dependencies while laying the groundwork for more advanced enhancements in later phases.