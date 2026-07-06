from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Tag:
    """Radarr tag model."""

    id: int
    label: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Tag':
        """Create a Tag from a dictionary.

        Args:
            data: Dictionary from Radarr API

        Returns:
            Tag object
        """
        return cls(
            id=data.get('id', 0),
            label=data.get('label', '')
        )


@dataclass
class Movie:
    """Radarr movie model.

    A read-only subset of the fields relevant for movie categorization and
    tag management.
    """

    id: int
    title: str

    # Optional metadata fields
    original_title: Optional[str] = None
    sort_title: Optional[str] = None
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    overview: Optional[str] = None
    runtime: Optional[int] = None  # Minutes
    genres: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    studio: Optional[str] = None
    certification: Optional[str] = None
    original_language: Optional[str] = None
    # Prompt-only signals: these drift over time, so they are deliberately
    # excluded from the metadata hash to avoid re-evaluation churn
    imdb_rating: Optional[float] = None
    rotten_tomatoes: Optional[int] = None

    # Status fields
    status: Optional[str] = None  # released, announced, etc.
    monitored: bool = True

    # Tag management
    tag_ids: List[int] = field(default_factory=list)

    # File system fields
    path: Optional[str] = None

    # Additional metadata
    quality_profile_id: Optional[int] = None
    youtube_trailer_id: Optional[str] = None
    collection: Dict[str, Any] = field(default_factory=dict)
    alternative_titles: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _rating(data: Dict[str, Any], source: str, ndigits: int = 0, as_int: bool = False):
        """Extract one rating value from Radarr's ratings blob, rounded."""
        value = ((data.get('ratings') or {}).get(source) or {}).get('value')
        if value is None or value == 0:
            return None
        return int(round(value)) if as_int else round(value, ndigits)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Movie':
        """Create a Movie from a dictionary.

        Args:
            data: Dictionary from Radarr API

        Returns:
            Movie object
        """
        return cls(
            id=data.get('id', 0),
            title=data.get('title', ''),
            original_title=data.get('originalTitle'),
            sort_title=data.get('sortTitle'),
            year=data.get('year'),
            tmdb_id=data.get('tmdbId'),
            imdb_id=data.get('imdbId'),
            overview=data.get('overview'),
            runtime=data.get('runtime'),
            genres=data.get('genres', []),
            keywords=data.get('keywords', []),
            tag_ids=data.get('tags', []),
            studio=data.get('studio'),
            certification=data.get('certification'),
            original_language=(data.get('originalLanguage') or {}).get('name'),
            imdb_rating=cls._rating(data, 'imdb', ndigits=1),
            rotten_tomatoes=cls._rating(data, 'rottenTomatoes', as_int=True),
            quality_profile_id=data.get('qualityProfileId'),
            monitored=data.get('monitored', True),
            status=data.get('status'),
            path=data.get('path'),
            youtube_trailer_id=data.get('youTubeTrailerId'),
            collection=data.get('collection', {}),
            alternative_titles=data.get('alternativeTitles', [])
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary for Radarr API.

        Returns:
            Dictionary for Radarr API
        """
        # Include all necessary fields for movie updates
        # Based on the Radarr API requirements for movie updates
        result = {
            'id': self.id,
            'title': self.title,
            'originalTitle': self.original_title,
            'sortTitle': self.sort_title,
            'year': self.year,
            'tmdbId': self.tmdb_id,
            'imdbId': self.imdb_id,
            'overview': self.overview,
            'monitored': self.monitored,
            'qualityProfileId': self.quality_profile_id,
            'tags': self.tag_ids,
            'path': self.path,
            'status': self.status,
            'runtime': self.runtime,
            'genres': self.genres,
            'studio': self.studio
        }

        # Filter out None values to avoid overwriting with null
        return {k: v for k, v in result.items() if v is not None}

    def calculate_metadata_hash(self) -> str:
        """Calculate a hash of movie metadata for change detection.

        Returns:
            Hash string
        """
        from kometa_ai.utils.helpers import compute_hash

        # Include fields relevant to classification
        metadata = {
            'title': self.title,
            'original_title': self.original_title,
            'year': self.year,
            'overview': self.overview,
            'genres': sorted(self.genres),
            'keywords': sorted(self.keywords),
            'certification': self.certification,
            'original_language': self.original_language,
            'studio': self.studio,
            'youtube_trailer_id': self.youtube_trailer_id,
            'alternative_titles': sorted(
                [title.get('title', '') for title in self.alternative_titles]
            ) if self.alternative_titles else []
        }

        # Include collection information if available
        if self.collection and 'name' in self.collection:
            metadata['collection'] = self.collection.get('name')

        return compute_hash(metadata)
