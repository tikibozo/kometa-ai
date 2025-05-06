import re
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from ruamel.yaml import YAML
from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.utils.helpers import slugify

logger = logging.getLogger(__name__)


class KometaParser:
    """Parser for Kometa configuration files."""

    # Patterns for AI configuration blocks
    START_MARKER = r"#\s*===\s*KOMETA-AI\s*===\s*"
    END_MARKER = r"#\s*===\s*END\s*KOMETA-AI\s*===\s*"
    TAG_PREFIX = "KAI-"

    def __init__(self, config_dir: str):
        """Initialize the parser.

        Args:
            config_dir: Path to the Kometa configuration directory
        """
        self.config_dir = Path(config_dir)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        # Check for environment variable to control tag correction
        self.auto_fix_tags = os.environ.get('KOMETA_FIX_TAGS', '').lower() in ('true', 'yes', '1')

    def find_yaml_files(self) -> List[Path]:
        """Find all YAML files in the configuration directory.

        Returns:
            List of YAML file paths
        """
        logger.debug(f"Searching for YAML files in {self.config_dir}")
        yaml_files = []

        for file_path in self.config_dir.glob('**/*.y*ml'):
            # Skip files prefixed with underscore or dot
            if file_path.name.startswith(('_', '.')):
                logger.debug(f"Skipping {file_path} (prefixed with _ or .)")
                continue

            yaml_files.append(file_path)

        logger.info(f"Found {len(yaml_files)} YAML files")
        return yaml_files

    def extract_ai_blocks(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        """Extract AI configuration blocks from a YAML file.

        Args:
            file_path: Path to the YAML file

        Returns:
            Dictionary of collection names to AI configurations
        """
        logger.debug(f"Extracting AI blocks from {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()

        # Find AI configuration blocks
        pattern = f"{self.START_MARKER}(.*?){self.END_MARKER}"
        blocks = re.finditer(pattern, content, re.DOTALL)

        # Extract the parent collection name for each block
        result = {}
        for block in blocks:
            try:
                block_text = block.group(1)

                # Find the collection name (next non-comment line after end marker)
                end_pos = block.end()
                lines_after = content[end_pos:].split('\n')
                collection_name = None

                for line in lines_after:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract collection name (assuming format: "Name:")
                        match = re.match(r'([^:]+):', line)
                        if match:
                            collection_name = match.group(1).strip()
                        break

                if not collection_name:
                    logger.warning(f"Could not determine collection name for AI block in {file_path}")
                    continue

                # Process the block with simplified approach
                config_dict = self.process_config_block(block_text)

                # Check radarr_taglist if this is an enabled collection
                if config_dict.get('enabled', False):
                    # Check if the radarr_taglist matches the expected format
                    is_valid, current_tag = self.check_radarr_taglist(file_path, collection_name)
                    if current_tag is not None:  # Only proceed if we found a radarr_taglist
                        if not is_valid:
                            expected_tag = self.get_expected_tag(collection_name)
                            logger.warning(
                                f"Mismatched tag for collection '{collection_name}' in {file_path}. "
                                f"Expected: {expected_tag}, Found: {current_tag}"
                            )
                            # Auto-fix if enabled
                            if self.auto_fix_tags:
                                if self.fix_radarr_taglist(file_path, collection_name, current_tag):
                                    logger.info(f"Fixed tag for collection '{collection_name}' in {file_path}")
                                else:
                                    logger.error(f"Failed to fix tag for collection '{collection_name}' in {file_path}")
                            else:
                                logger.info(
                                    "Set environment variable KOMETA_FIX_TAGS=true to automatically fix mismatched tags"
                                )

                # Log the result for debugging
                logger.debug(f"Extracted config for {collection_name}: {config_dict}")
                result[collection_name] = config_dict

            except Exception as e:
                logger.error(f"Error parsing block in {file_path}: {str(e)}")
                continue

        return result

    def get_expected_tag(self, collection_name: str) -> str:
        """Get the expected tag for a collection.

        Args:
            collection_name: Collection name

        Returns:
            Expected tag in the format "KAI-<slugified-name>"
        """
        return f"{self.TAG_PREFIX}{slugify(collection_name)}"
    
    def check_radarr_taglist(self, file_path: Path, collection_name: str) -> Tuple[bool, Optional[str]]:
        """Check if the radarr_taglist for a collection matches the expected format.

        Args:
            file_path: Path to the YAML file
            collection_name: Collection name

        Returns:
            Tuple of (is_valid, current_value) where is_valid is True if the tag matches the expected format
        """
        # Load the YAML file
        with open(file_path, 'r') as f:
            try:
                data = self.yaml.load(f)
            except Exception as e:
                logger.error(f"Error loading YAML file {file_path}: {e}")
                return False, None
                
        if not data or not isinstance(data, dict) or 'collections' not in data:
            logger.warning(f"No collections found in {file_path}")
            return False, None
            
        collections = data.get('collections', {})
        if not collections or collection_name not in collections:
            logger.warning(f"Collection '{collection_name}' not found in {file_path}")
            return False, None
            
        collection_data = collections[collection_name]
        if not isinstance(collection_data, dict) or 'radarr_taglist' not in collection_data:
            logger.warning(f"No radarr_taglist found for collection '{collection_name}' in {file_path}")
            return False, None
            
        current_tag = collection_data['radarr_taglist']
        expected_tag = self.get_expected_tag(collection_name)
        
        return current_tag == expected_tag, current_tag
    
    def fix_radarr_taglist(self, file_path: Path, collection_name: str, current_tag: str) -> bool:
        """Fix the radarr_taglist for a collection.

        Args:
            file_path: Path to the YAML file
            collection_name: Collection name
            current_tag: Current radarr_taglist value

        Returns:
            True if the fix was applied successfully
        """
        expected_tag = self.get_expected_tag(collection_name)
        
        # Read the file content as text
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Create a pattern to find the radarr_taglist line for this collection
        # This is more reliable than modifying the YAML structure directly, as it preserves formatting
        pattern = fr'({collection_name}:(?:\s*\n\s+.*)*\s+radarr_taglist:\s*)({re.escape(current_tag)})'
        replacement = fr'\1{expected_tag}'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content == content:
            logger.warning(f"Failed to replace tag in {file_path} for '{collection_name}'")
            return False
            
        # Write the modified content back to the file
        with open(file_path, 'w') as f:
            f.write(new_content)
            
        logger.info(f"Fixed radarr_taglist for '{collection_name}' in {file_path}: {current_tag} -> {expected_tag}")
        return True
    
    def process_config_block(self, block_text: str) -> Dict[str, Any]:
        """Process a configuration block and extract key-value pairs.

        Args:
            block_text: Text of the configuration block

        Returns:
            Dictionary of configuration key-value pairs
        """
        config = {}

        # Split into lines
        lines = block_text.split('\n')

        # Track for prompt processing
        prompt_lines = []
        in_prompt = False
        prompt_indent = ""  # Track the indentation of the prompt content

        # First pass: Identify all regular keys that come before 'prompt'
        regular_keys = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or not stripped.startswith('#'):
                continue

            # Remove comment marker but keep indentation
            if stripped.startswith('# '):
                cleaned = stripped[2:]
            else:
                cleaned = stripped[1:]

            # Identify the prompt start
            if ':' in cleaned and 'prompt:' in cleaned.lower():
                # Found the prompt, no need to continue first pass
                break

            # Track regular keys before the prompt
            if ':' in cleaned:
                regular_keys.append((i, cleaned))

        # Now process all lines
        for i, line in enumerate(lines):
            # Skip empty lines
            stripped = line.strip()
            if not stripped or not stripped.startswith('#'):
                continue

            # Remove comment marker but keep indentation
            if stripped.startswith('# '):
                cleaned = stripped[2:]
            else:
                cleaned = stripped[1:]

            logger.debug(f"Processing line {i}: '{cleaned}'")

            # If we're already collecting prompt content
            if in_prompt:
                # Check if we've reached another key-value pair after the prompt
                # This helps us handle cases where priority, confidence_threshold, etc.
                # come after the prompt block

                # Only consider it a new key if it's at the same indentation level as the original keys
                # and it's a simple word (no spaces) followed by a colon
                if (not cleaned.startswith(prompt_indent) and
                        ':' in cleaned and
                        len(cleaned.split(':')[0].strip().split()) == 1):

                    # Looks like we've reached the end of the prompt content
                    # Process this as a regular key-value pair
                    in_prompt = False

                    key, value = cleaned.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    config[key] = value
                    logger.debug(f"Found key-value after prompt: '{key}': '{value}'")
                    continue

                # Otherwise, still part of the prompt
                prompt_lines.append(cleaned)
                logger.debug(f"Added to prompt: '{cleaned}'")
                continue

            # Check if this is the start of a prompt
            if ':' in cleaned and 'prompt:' in cleaned.lower():
                key, value = cleaned.split(':', 1)
                key = key.strip()
                value = value.strip()

                if value == '|':
                    # Start of multi-line prompt
                    in_prompt = True
                    # Determine the indentation level expected for prompt content
                    # by checking the leading whitespace of the line
                    indent_match = re.match(r'^(\s*)', cleaned)
                    if indent_match:
                        prompt_indent = indent_match.group(1)
                    logger.debug(f"Starting prompt collection with indent level: '{prompt_indent}'")
                else:
                    # Single line prompt
                    config[key] = value
                    logger.debug(f"Single line prompt: '{value}'")
            elif ':' in cleaned:
                # Regular key-value pair
                key, value = cleaned.split(':', 1)
                key = key.strip()
                value = value.strip()
                config[key] = value
                logger.debug(f"Found key-value: '{key}': '{value}'")

        # Add the collected prompt content
        if in_prompt and prompt_lines:
            # Clean up the prompt lines
            # Remove configurations that might have been captured in the prompt
            clean_prompt_lines = []
            for line in prompt_lines:
                # Skip lines that look like other config parameters
                skip_patterns = [
                    r'^confidence_threshold:\s',
                    r'^priority:\s',
                    r'^enabled:\s',
                    r'^use_iterative_refinement:\s',
                    r'^refinement_threshold:\s'
                ]

                should_skip = False
                for pattern in skip_patterns:
                    if re.match(pattern, line.strip()):
                        logger.debug(f"Skipping config line from prompt: '{line}'")
                        should_skip = True
                        break

                if not should_skip:
                    # Add to clean prompt
                    clean_prompt_lines.append(line)

            prompt_text = '\n'.join(clean_prompt_lines)
            config['prompt'] = prompt_text
            logger.debug(f"Final prompt (length: {len(prompt_text)}): '{prompt_text}'")

        # Convert types for specific keys
        if 'enabled' in config:
            # Save to a temp variable to avoid type error
            enabled_value = str(config['enabled']).lower() in ('true', 'yes', '1')
            config['enabled'] = enabled_value  # type: ignore

        if 'confidence_threshold' in config:
            try:
                # Save to a temp variable to avoid type error
                threshold_value = float(config['confidence_threshold'])
                config['confidence_threshold'] = threshold_value  # type: ignore
            except ValueError:
                config['confidence_threshold'] = 0.7  # type: ignore

        if 'priority' in config:
            try:
                # Save to a temp variable to avoid type error
                priority_value = int(config['priority'])
                config['priority'] = priority_value  # type: ignore
            except ValueError:
                config['priority'] = 0  # type: ignore
                
        # New options for iterative refinement
        if 'use_iterative_refinement' in config:
            # Save to a temp variable to avoid type error
            refinement_value = str(config['use_iterative_refinement']).lower() in ('true', 'yes', '1')
            config['use_iterative_refinement'] = refinement_value  # type: ignore
            
        if 'refinement_threshold' in config:
            try:
                # Save to a temp variable to avoid type error
                threshold_value = float(config['refinement_threshold'])
                config['refinement_threshold'] = threshold_value  # type: ignore
            except ValueError:
                config['refinement_threshold'] = 0.15  # type: ignore

        return config

    def parse_configs(self) -> List[CollectionConfig]:
        """Parse all AI collection configurations.

        Returns:
            List of collection configurations
        """
        logger.info("Parsing AI collection configurations")
        configs = {}

        for file_path in self.find_yaml_files():
            try:
                file_configs = self.extract_ai_blocks(file_path)
                for collection_name, config_dict in file_configs.items():
                    # If collection was already found in another file, merge configs
                    if collection_name in configs:
                        logger.warning(
                            f"Collection '{collection_name}' found in multiple files, "
                            f"using configuration from {file_path}"
                        )

                    configs[collection_name] = config_dict
            except Exception as e:
                logger.error(f"Error parsing file {file_path}: {e}")

        # Convert to CollectionConfig objects
        result = []
        for collection_name, config_dict in configs.items():
            try:
                # Add better logging for troubleshooting
                logger.debug(f"Creating config for '{collection_name}' with data: {config_dict}")

                # Ensure 'prompt' key exists
                if 'prompt' not in config_dict:
                    logger.warning(f"No prompt found for collection '{collection_name}', using empty prompt")
                    config_dict['prompt'] = ""

                config = CollectionConfig.from_dict(collection_name, config_dict)
                logger.debug(f"Created config with prompt: {config.prompt[:100]}...")
                result.append(config)
            except Exception as e:
                logger.error(f"Error creating configuration for '{collection_name}': {e}")

        # Filter to only enabled collections
        enabled_configs = [config for config in result if config.enabled]
        logger.info(f"Found {len(enabled_configs)} enabled AI collections out of {len(result)} total")

        # Sort by priority (higher first)
        enabled_configs.sort(key=lambda x: x.priority, reverse=True)

        return enabled_configs
