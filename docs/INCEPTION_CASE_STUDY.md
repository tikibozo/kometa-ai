# Case Study: Inception in Heist Movies Collection

## The Problem

You mentioned that "Inception" is currently being included in the "Heist Movies" collection in our test data, which doesn't accurately reflect its primary genre classification. Let's analyze why this is happening and how our proposed solutions would address this specific case.

## Why It's Happening

### Current Radarr Overview of Inception

Looking at our code, Claude is primarily receiving the "overview" property when evaluating movies. A typical Radarr overview for Inception might read:

> "Cobb, a skilled thief who commits corporate espionage by infiltrating the subconscious of his targets is offered a chance to regain his old life as payment for a task considered to be impossible: 'inception', the implantation of another person's idea into a target's subconscious."

### Why This Causes Confusion

When only given this brief description and the following criteria for Heist Movies:
- Central plot revolves around planning and executing a heist or robbery
- Features a team assembling a plan to steal something valuable
- Includes planning, preparation, and execution

It's understandable why Claude might classify Inception as a heist movie:
1. The overview explicitly mentions "thief" and "corporate espionage"
2. It describes infiltrating and stealing/implanting something (ideas)
3. It suggests team planning and execution

Without broader context about the sci-fi dream elements being the primary focus and genre of the film, Claude is making a reasonable assessment based on limited information.

## How Our Solutions Would Address This

### 1. Enhanced Prompt Engineering

With our enhanced system prompt, we explicitly direct Claude to:
- "Evaluate the movie's actual content and themes, not just what's mentioned in the overview"
- "Be discriminating: a movie containing elements of a genre doesn't necessarily mean it belongs in that collection"
- "Consider the movie's primary themes and genres, not incidental elements"

Additionally, by adding explicit examples like:
```yaml
example_exclusions:
  - title: "Inception"
    year: 2010
    reason: "While it has elements of a heist (stealing ideas), it's primarily a sci-fi movie about dreams"
```

We directly address this specific misclassification.

### 2. Iterative Refinement

If Inception came back as a borderline case, our iterative refinement would prompt Claude with:

```
I need your help analyzing whether the movie "Inception" (2010) should be included in the "Heist Movies" collection.

This is a borderline case that needs deeper analysis. Please use your knowledge of films to thoroughly analyze this movie beyond the basic information provided. Consider:

1. The primary themes and focus of the movie
2. The genre conventions the movie follows
3. Whether the collection theme is central to the movie or just incidental
...
```

This would allow Claude to leverage its broader knowledge about Inception, recognizing that:
- The primary genre is science fiction
- The central themes are dreams, reality, and grief
- The heist element is a plot device within a larger sci-fi framework
- The film is widely categorized as sci-fi/thriller, not as a heist film

### 3. External Data Integration (Future Phase)

In future phases, we could obtain additional context such as:
- TMDB genre tags: "Science Fiction, Action, Adventure"
- TMDB keywords: "dream, subconscious, mind, perception, reality"
- Plot synopsis mentioning the multiple dream levels and sci-fi elements

This additional data would make it much clearer that while Inception has heist elements, they're secondary to its sci-fi premise.

## Measuring Improvement

To track whether our changes are improving classification accuracy, we could:

1. Create a benchmark test set of movies with known-correct classifications
2. Include several edge cases like Inception that have elements of multiple genres
3. Run this set through both our current system and improved system
4. Compare accuracy rates between the two

For the Inception case specifically, we would check if:
- It's correctly excluded from "Heist Movies"
- It's correctly included in "Science Fiction"
- The confidence scores reflect appropriate certainty levels

This benchmark would help us quantify improvements and identify areas for further refinement.