# Debugging YAML Parsing in Kometa-AI

This document provides some tips for debugging the YAML parsing issues in Kometa-AI, particularly for multi-line prompts with bullet points.

## How to Read Debug Logs

When running Kometa-AI with `DEBUG_LOGGING=true`, you should see detailed logs about the YAML parsing process. Look for these key log patterns:

1. **Raw Line Processing**: Shows the raw lines being processed
   ```
   Processing line X: '# prompt: |'
   ```

2. **Cleaned Line**: Shows the line after comment markers are removed
   ```
   Cleaned line: 'prompt: |'
   ```

3. **Multi-line Value Start**: Shows when a multi-line value starts
   ```
   Starting multi-line value for key 'prompt'
   ```

4. **Multi-line Value Addition**: Shows lines being added to a multi-line value
   ```
   Adding line to multi-line value: '  Identify film noir movies based on these criteria:'
   Adding line to multi-line value: '  - Made primarily between 1940-1959'
   ```

5. **Multi-line Value End**: Shows when a multi-line value ends
   ```
   Ending multi-line value for key 'prompt' with X lines
   ```

6. **Final Prompt Processing**: Shows the full prompt after extraction
   ```
   Collection prompt (type: <class 'str'>): 'Identify film noir...'
   ```

## Troubleshooting

If you're still experiencing issues with multi-line prompts:

1. **Check Comment Format**: Ensure your YAML comments use consistent formatting:
   ```yaml
   # prompt: |
   #   Identify film noir movies based on these criteria:
   #   - Made primarily between 1940-1959
   ```
   Note the two spaces of indentation after the comment marker in the content lines.

2. **Check Transition Between Key-Value and List Items**: Make sure there's a clear distinction between key-value pairs and list items:
   ```yaml
   # prompt: |
   #   Header line
   #   - List item 1
   #   - List item 2
   # confidence_threshold: 0.7  # New key, clearly separated
   ```

3. **Verify No Blank Lines**: Avoid blank comment lines in the middle of multi-line values:
   ```yaml
   # prompt: |
   #   Line 1
   #   # This blank comment line might cause problems
   #   Line 2
   ```

4. **Check for Invisible Characters**: Sometimes invisible characters might cause parsing issues. Try re-typing problematic sections.

## Manual Testing

You can manually test the YAML parsing with this simple Python script:

```python
import re
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Sample YAML block
yaml_block = """# === KOMETA-AI ===
# enabled: true
# prompt: |
#   Identify film noir movies based on these criteria:
#   - Made primarily between 1940-1959
#   - Dark, cynical themes and moral ambiguity
#   - Visual style emphasizing shadows, unusual angles
#   - Crime or detective storylines
#   - Femme fatale character often present
# confidence_threshold: 0.7
# === END KOMETA-AI ===""".split('\n')

# Test parsing
current_key = None
current_value = None
is_multiline = False
config_dict = {}

for i, line in enumerate(yaml_block):
    logger.debug(f"Processing line {i}: '{line}'")
    
    stripped_line = line.strip()
    if not stripped_line or not stripped_line.startswith('#'):
        continue
    
    # Remove comment marker but preserve indentation
    if stripped_line.startswith('# '):
        cleaned_line = stripped_line[2:]
    else:
        cleaned_line = stripped_line[1:]
    
    logger.debug(f"Cleaned line: '{cleaned_line}'")
    
    # Check if this is a key-value pair
    if ':' in cleaned_line and not is_multiline and not cleaned_line.strip().startswith('-'):
        # Store previous key-value if exists
        if current_key:
            if isinstance(current_value, list):
                logger.debug(f"Storing key '{current_key}' with list value of length {len(current_value)}")
                config_dict[current_key] = '\n'.join(current_value)
            else:
                logger.debug(f"Storing key '{current_key}' with simple value: '{current_value}'")
                config_dict[current_key] = current_value
        
        # Extract new key-value
        key_part, value_part = cleaned_line.split(':', 1)
        current_key = key_part.strip()
        current_value = value_part.strip()
        
        logger.debug(f"Found key-value: '{current_key}': '{current_value}'")
        
        # Check if this is a multi-line value
        if current_value == '|':
            logger.debug(f"Starting multi-line value for key '{current_key}'")
            is_multiline = True
            current_value = []
    
    # If we're in a multi-line value, collect the lines
    elif is_multiline:
        # Check if this is a new key (which would end the multi-line value)
        if ':' in cleaned_line and not cleaned_line.strip().startswith('-'):
            # Store multi-line value
            logger.debug(f"Ending multi-line value for key '{current_key}' with {len(current_value)} lines")
            config_dict[current_key] = '\n'.join(current_value)
            
            # Start new key-value
            key_part, value_part = cleaned_line.split(':', 1)
            current_key = key_part.strip()
            current_value = value_part.strip()
            logger.debug(f"Found new key-value: '{current_key}': '{current_value}'")
            
            is_multiline = (current_value == '|')
            if is_multiline:
                logger.debug(f"Starting new multi-line value for key '{current_key}'")
                current_value = []
        else:
            # Add to multi-line value
            logger.debug(f"Adding line to multi-line value: '{cleaned_line}'")
            current_value.append(cleaned_line.rstrip())

# Store last key-value if exists
if current_key:
    if is_multiline:
        config_dict[current_key] = '\n'.join(current_value)
    else:
        config_dict[current_key] = current_value

# Print result
logger.debug("Final config:")
for key, value in config_dict.items():
    logger.debug(f"  {key}: {value!r}")
```

This script can help identify exactly where the parsing is failing.