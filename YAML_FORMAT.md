# Kometa AI Collection Configuration Format

This document explains the format for defining AI-powered collections in Kometa-AI.

## Basic Structure

Collections are defined in YAML files within the `kometa-config` directory. Each collection has a special comment block that defines its AI behavior:

```yaml
# === KOMETA-AI ===
# enabled: true
# confidence_threshold: 0.7
# prompt: |
#   Identify film noir movies based on these criteria:
#   - Made primarily between 1940-1959
#   - Dark, cynical themes and moral ambiguity
#   - Visual style emphasizing shadows, unusual angles
#   - Crime or detective storylines
#   - Femme fatale character often present
# === END KOMETA-AI ===
Film Noir:
  plex_search:
    all:
      genre: Film-Noir
```

## Configuration Options

Each AI collection supports the following configuration options:

| Option | Description | Default | Required |
| ------ | ----------- | ------- | -------- |
| `enabled` | Whether the collection is active | `false` | Yes |
| `prompt` | The instructions for Claude AI (multi-line) | None | Yes |
| `confidence_threshold` | Minimum confidence score (0.0-1.0) | `0.7` | No |
| `priority` | Collection processing order (higher = earlier) | `0` | No |
| `include_tags` | Tags that should always be included | `[]` | No |
| `exclude_tags` | Tags that should always be excluded | `[]` | No |

## Multi-line Prompts

For prompts with multiple lines, use the YAML pipe character (`|`) after `prompt:` to start a multi-line block:

```yaml
# prompt: |
#   This is a multi-line prompt
#   With several lines of text
```

## Including Bullet Points

You can use bullet points in your prompts:

```yaml
# prompt: |
#   Identify movies that match these criteria:
#   - First criterion
#   - Second criterion
#   - Third criterion
```

## Order of Configuration Options

The order of configuration options is important:

1. Place all standard configuration options (enabled, confidence_threshold, priority, etc.) FIRST
2. Always place the `prompt` option LAST, right before the END marker
3. Use the multi-line format (`|`) for any prompt with multiple lines or bullet points

This ordering ensures that configuration options aren't accidentally included in the prompt content.

## Important Notes

1. Each configuration option must be on its own line and prefixed with `#`.
2. Each line of the prompt (and bullet points) must be prefixed with `#`.
3. The AI block must begin with `# === KOMETA-AI ===` and end with `# === END KOMETA-AI ===`.
4. The Kometa collection name must immediately follow the end marker.
5. **REQUIRED ORDER**: Standard configuration options FIRST, prompt LAST.
6. The `prompt` must be placed immediately before the `=== END KOMETA-AI ===` marker.

## Example Files

For examples of properly formatted collections, see:
- `kometa-config/collections.yml` - Production collections
- `kometa-config/sample_collections.yml` - Example collections with different formats

## Parser Behavior

The parser will:
1. Extract all configuration blocks marked with `KOMETA-AI` tags
2. Parse configuration options (enabled, confidence_threshold, priority, etc.)
3. Extract the multi-line prompt, preserving all text including bullet points
4. Filter out configuration lines that might accidentally be included in the prompt

This ensures that all bullet points and formatting in your prompt are preserved when sent to Claude AI.