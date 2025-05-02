# Parser Fix: Multi-line Prompts with Bullet Points

## Issue Description

The original YAML parser had difficulty correctly handling multi-line prompts containing bullet points, especially when the bullet points contained colons. Key issues included:

1. The parser incorrectly treated bullet point lines with colons as separate key-value pairs
2. Configuration options like `confidence_threshold` and `priority` that appeared after the prompt were being included in the prompt text
3. The indentation levels were not consistently preserved for bullet points

## Solution Implemented

We've completely rewritten the `process_config_block` method in the `KometaParser` class to address these issues:

1. Better detection of multi-line prompts using the pipe symbol (`|`)
2. Improved handling of bullet point lines (starting with `-`) 
3. Filtering out configuration lines from the prompt text
4. Tracking indentation levels to differentiate between prompt content and regular configuration keys

The new parser explicitly checks and removes configuration lines like `confidence_threshold:` and `priority:` that might be captured as part of the prompt content.

## Key Changes

1. **Removed duplicate code**: Eliminated the `fix_parser.py` module and updated the original `parser.py` instead.

2. **Simplified parsing logic**: The new implementation explicitly separates the prompt collection from other configuration options.

3. **Added post-processing cleanup**: We now filter out configuration lines that were captured as part of the prompt.

4. **Improved logging**: Added detailed logging about the prompt content, including line-by-line examination, to help with debugging.

5. **Enhanced prompt inspection in Claude**: Updated the Claude `prompts.py` module to provide more detailed logging about the prompts it receives.

6. **Required configuration ordering**: Established a strict order for configurations:
   - Standard configuration options (enabled, confidence_threshold, etc.) must come FIRST
   - The `prompt` option must come LAST, right before the END marker
   - This ordering helps prevent configuration options from being accidentally included in the prompt

## Testing

We've created a `test_parser.py` script that verifies the parser can correctly handle multi-line prompts with bullet points. This script:

1. Parses all collection configurations
2. Displays the parsed prompts and configuration
3. Verifies bullet points are preserved
4. Checks if configuration options are correctly separated from prompt content
5. Validates that the parser works with the required ordering (config options first, prompt last)

The updated collection examples all follow the required ordering convention, with standard configuration options first and the prompt last (right before the END marker).

## Documentation

Created a new `YAML_FORMAT.md` file that explains:

1. The expected format for collection configuration
2. How to define multi-line prompts with bullet points
3. The supported configuration options
4. Examples of correctly formatted collections

## Validation

Testing confirms that bullet points in collection prompts are now correctly preserved and displayed in the prompt sent to Claude AI. Configuration options like `confidence_threshold` and `priority` are properly parsed as separate configuration options rather than being included in the prompt text.

## Future Improvements

While the current implementation is robust, future improvements could include:

1. Formal validation of collection configurations
2. Better error reporting for malformed configurations
3. Support for more structured prompt formats
4. A visual editor for collection configurations