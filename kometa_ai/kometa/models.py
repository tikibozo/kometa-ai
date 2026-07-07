from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


def _as_str_list(value: Any) -> List[str]:
    """Coerce a block value into a clean list of strings.

    Accepts an actual list or a comma-separated string (how the KOMETA-AI
    comment block delivers it), dropping blanks.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _as_opt_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


@dataclass
class CollectionConfig:
    """Configuration for an AI-managed collection."""

    name: str
    slug: str
    enabled: bool = False
    prompt: str = ""
    confidence_threshold: float = 0.7
    priority: int = 0
    exclude_tags: List[str] = field(default_factory=list)
    include_tags: List[str] = field(default_factory=list)

    # Candidate prefilter (Lever 1). A coarse, zero-cost metadata gate applied
    # before any Claude evaluation: movies that can't plausibly belong are
    # excluded deterministically so a large library isn't paid for in full on
    # every new/changed collection. All gates are opt-in and fail OPEN — a
    # movie missing the data being gated on is kept as a candidate, so the
    # filter only ever removes movies we're confident are non-members.
    candidate_genres: List[str] = field(default_factory=list)
    candidate_exclude_genres: List[str] = field(default_factory=list)
    candidate_year_min: Optional[int] = None
    candidate_year_max: Optional[int] = None

    @property
    def tag(self) -> str:
        """Get the Radarr tag for this collection.

        Returns:
            Radarr tag string
        """
        return f"KAI-{self.slug}"

    def is_candidate(self, movie: Any) -> bool:
        """Whether a movie passes the coarse candidate prefilter.

        Returns True when the movie could plausibly belong (and so is worth a
        Claude evaluation). Every gate fails open: if the data a gate needs is
        absent on the movie, the gate does not exclude it. With no gates
        configured this is always True (a no-op).
        """
        genres = {g.lower() for g in (getattr(movie, "genres", None) or [])}

        if self.candidate_genres and genres:
            wanted = {g.lower() for g in self.candidate_genres}
            if genres.isdisjoint(wanted):
                return False

        if self.candidate_exclude_genres and genres:
            unwanted = {g.lower() for g in self.candidate_exclude_genres}
            if genres & unwanted:
                return False

        year = getattr(movie, "year", None)
        if year is not None:
            if self.candidate_year_min is not None and year < self.candidate_year_min:
                return False
            if self.candidate_year_max is not None and year > self.candidate_year_max:
                return False

        return True

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'CollectionConfig':
        """Create a CollectionConfig from a dictionary.

        Args:
            name: Collection name
            data: Dictionary from parsed YAML

        Returns:
            CollectionConfig object
        """
        from kometa_ai.utils.helpers import slugify

        return cls(
            name=name,
            slug=slugify(name),
            enabled=data.get('enabled', False),
            prompt=data.get('prompt', ''),
            confidence_threshold=float(data.get('confidence_threshold', 0.7)),
            priority=int(data.get('priority', 0)),
            exclude_tags=data.get('exclude_tags', []),
            include_tags=data.get('include_tags', []),
            candidate_genres=_as_str_list(data.get('candidate_genres')),
            candidate_exclude_genres=_as_str_list(data.get('candidate_exclude_genres')),
            candidate_year_min=_as_opt_int(data.get('candidate_year_min')),
            candidate_year_max=_as_opt_int(data.get('candidate_year_max')),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'slug': self.slug,
            'enabled': self.enabled,
            'prompt': self.prompt,
            'confidence_threshold': self.confidence_threshold,
            'priority': self.priority,
            'exclude_tags': self.exclude_tags,
            'include_tags': self.include_tags,
            'candidate_genres': self.candidate_genres,
            'candidate_exclude_genres': self.candidate_exclude_genres,
            'candidate_year_min': self.candidate_year_min,
            'candidate_year_max': self.candidate_year_max,
        }
