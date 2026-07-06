import re
import hashlib
import json
from typing import Any, Dict, List, Union


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

