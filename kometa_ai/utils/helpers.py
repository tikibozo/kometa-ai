import re
import hashlib
import json
from typing import Any, Dict, List, Optional, Union


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: The text to slugify

    Returns:
        The slugified text
    """
    # Convert to lowercase
    text = text.lower()

    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)

    # Remove non-alphanumeric characters (except hyphens)
    text = re.sub(r'[^a-z0-9-]', '', text)

    # Remove multiple hyphens
    text = re.sub(r'-+', '-', text)

    # Remove leading/trailing hyphens
    text = text.strip('-')

    return text


def compute_hash(data: Union[str, Dict[str, Any], List[Any]]) -> str:
    """Compute a hash of the given data.

    Args:
        data: Data to hash (string or JSON-serializable object)

    Returns:
        Hexadecimal hash string
    """
    if not isinstance(data, str):
        # Convert to a deterministic JSON string
        data = json.dumps(data, sort_keys=True)

    # Compute SHA-256 hash
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with dict2 taking precedence over dict1.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (overrides values from dict1)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    result.update(dict2)
    return result


def dict_path_get(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from a nested dictionary using a dot-separated path.

    Args:
        data: The dictionary to get the value from
        path: Dot-separated path to the value (e.g., "a.b.c")
        default: Default value if the path is not found

    Returns:
        The value at the path or the default
    """
    parts = path.split('.')
    current = data

    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]

    return current


def dict_path_set(data: Dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dictionary using a dot-separated path.

    Args:
        data: The dictionary to set the value in
        path: Dot-separated path to the value (e.g., "a.b.c")
        value: The value to set
    """
    parts = path.split('.')
    current = data

    # Navigate to the parent of the leaf
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    # Set the leaf value
    current[parts[-1]] = value
