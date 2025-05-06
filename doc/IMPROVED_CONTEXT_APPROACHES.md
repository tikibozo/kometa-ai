# Approaches to Improve Collection Confidence Accuracy

## Current Limitations

After reviewing the codebase, I've identified that we're currently relying primarily on limited movie metadata when evaluating collection suitability with Claude:

1. The "overview" property from Radarr, which typically contains just a few sentences about the movie
2. Basic metadata like title, year, genres, and studio
3. Alternative titles when available

As illustrated by the Inception example (wrongly included in "Heist Movies" based on the plot overview), this limited context can lead to inaccurate categorization.

## Proposed Approaches

### 1. External API Enrichment

**Method**: Integrate with additional movie data APIs to gather more comprehensive information.

**Implementation Options**:
- **TMDB Extended Data**: Use the TMDb ID we already have to fetch additional information from The Movie Database API:
  - Full plot synopsis (longer than overview)
  - Keywords and themes
  - Production companies
  - Cast and crew details
  - Similar movies
- **OMDB API**: Provides more detailed plot descriptions, awards information, and ratings
- **IMDb API**: Access to detailed plot summaries, keywords, and goofs

**Pros**:
- Reliable, structured data
- Covers most commercial movies
- Many APIs offer free tiers

**Cons**:
- Rate limiting could slow processing
- Additional development work for API integration
- Some services require paid subscriptions

### 2. Web Scraping for Enhanced Descriptions

**Method**: Dynamically fetch richer descriptions from film databases or review sites.

**Implementation Options**:
- Scrape extended descriptions from Wikipedia
- Extract movie themes and analysis from review sites
- Parse movie critique sites for thematic analysis

**Pros**:
- Can obtain very detailed contextual information
- Access to critics' analysis of themes and genres

**Cons**:
- Legal and TOS considerations
- Website structure changes can break scrapers
- Rate limiting and blocking concerns

### 3. Iterative Refinement with Claude

**Method**: Use a multi-pass approach with Claude to refine decisions.

**Implementation Options**:
- **First Pass**: Basic evaluation using existing metadata
- **Second Pass**: For borderline cases (confidence near threshold), ask Claude to research and analyze the movie using its own knowledge
- **Final Pass**: Reconciliation of both analyses

**Pros**:
- Leverages Claude's knowledge without external APIs
- Focuses additional resources on only the borderline cases
- Simpler implementation, no external dependencies

**Cons**:
- Increased token usage for multi-pass processing
- Still limited by Claude's knowledge cutoff date

### 4. Embedded Vector Search for Similar Movies

**Method**: Build a vector database of known collection examples to find similarities.

**Implementation Options**:
- Embed movie descriptions using embedding models
- For each collection, maintain vector representations of confirmed members
- Use similarity search to help evaluate new movies

**Pros**:
- Can capture subtle thematic connections
- Gets better over time as the system learns
- Reduced reliance on explicit description content

**Cons**:
- Requires implementing vector storage and search
- Cold start problem for new collections

### 5. Prompt Engineering Improvements

**Method**: Enhance the prompts to help Claude make better decisions with existing data.

**Implementation Options**:
- **Negative Examples**: Include examples of movies that might seem to fit but shouldn't be included
- **Specific Theme Extraction**: Ask Claude to identify specific themes first, then evaluate
- **Template Overrides**: Allow collection configuration to include custom prompts for specific genres/themes

**Pros**:
- Minimal implementation effort
- No external dependencies
- Can be implemented immediately

**Cons**:
- Still limited by the data available
- Requires careful prompt crafting
- May not solve fundamental information gap

### 6. User Feedback Integration

**Method**: Allow users to correct classifications and learn from those corrections.

**Implementation Options**:
- Add user feedback mechanism via API endpoint
- Store user corrections in the state file
- Integrate corrections into future evaluation prompts

**Pros**:
- Directly addresses specific problem cases
- Improves over time with usage
- Creates a virtuous feedback loop

**Cons**:
- Requires user interface changes
- Complicated state tracking for user preferences

### 7. Pre-computed Movie Content Analysis

**Method**: Run initial Claude analysis on each movie to extract themes, motifs, and style in isolation from collections.

**Implementation Options**:
- **One-time Analysis**: When movies are added to the library, run a detailed Claude analysis
- Store these detailed analyses as part of the movie metadata hash
- Use this enhanced data during collection evaluation

**Pros**:
- Single up-front cost for detailed analysis
- Deeper understanding of each movie before collection assignment
- Reusable across multiple collections

**Cons**:
- Additional processing and storage requirements
- Upfront Claude API costs

## Recommended Implementation Strategy

Given the constraints and goals of the project, I recommend implementing a combination approach:

1. **First Phase** (immediate improvements):
   - Enhance prompt engineering (Approach #5)
   - Implement iterative refinement for borderline cases (Approach #3)

2. **Second Phase** (medium complexity):
   - Integrate with TMDB Extended Data API (Approach #1)
   - Add pre-computed movie content analysis (Approach #7)

3. **Third Phase** (longer-term improvements):
   - Implement user feedback integration (Approach #6)
   - Build vector similarity search for collection matching (Approach #4)

This staged approach allows for immediate improvements while building toward a more sophisticated system over time.