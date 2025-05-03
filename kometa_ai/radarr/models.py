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

    This represents a movie in Radarr. Note that for Stage 1, we're only
    implementing a read-only subset of the fields that are relevant for
    movie categorization and tag management.
    """

    # Required fields
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
    studio: Optional[str] = None

    # Status fields
    status: Optional[str] = None  # released, announced, etc.
    monitored: bool = True
    has_file: bool = False

    # Tag management
    tag_ids: List[int] = field(default_factory=list)

    # File system fields
    path: Optional[str] = None
    folder_name: Optional[str] = None
    size_on_disk: Optional[int] = None

    # Additional metadata
    quality_profile_id: Optional[int] = None
    added: Optional[str] = None  # ISO date
    ratings: Dict[str, Any] = field(default_factory=dict)
    youtube_trailer_id: Optional[str] = None
    collection: Dict[str, Any] = field(default_factory=dict)
    alternative_titles: List[Dict[str, Any]] = field(default_factory=list)

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
            tag_ids=data.get('tags', []),
            studio=data.get('studio'),
            quality_profile_id=data.get('qualityProfileId'),
            monitored=data.get('monitored', True),
            status=data.get('status'),
            added=data.get('added'),
            ratings=data.get('ratings', {}),
            path=data.get('path'),
            folder_name=data.get('folderName'),
            size_on_disk=data.get('sizeOnDisk'),
            has_file=data.get('hasFile', False),
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
