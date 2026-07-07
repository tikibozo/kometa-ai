"""Tests for the candidate prefilter (Lever 1): the coarse, zero-cost metadata
gate on CollectionConfig, and its parsing from the KOMETA-AI block."""

from kometa_ai.kometa.models import CollectionConfig
from kometa_ai.radarr.models import Movie


def cfg(**kw):
    return CollectionConfig(name="Test", slug="test", enabled=True, prompt="x", **kw)


def movie(genres=None, year=2000):
    return Movie(id=1, title="M", year=year, genres=genres or [])


def test_no_filter_is_noop():
    """With no gates configured, everything is a candidate."""
    c = cfg()
    assert c.is_candidate(movie(genres=["Romance"], year=1950)) is True


def test_candidate_genres_gate():
    c = cfg(candidate_genres=["Crime", "Thriller"])
    assert c.is_candidate(movie(genres=["Crime", "Drama"])) is True   # shares one
    assert c.is_candidate(movie(genres=["Romance", "Comedy"])) is False


def test_candidate_genres_case_insensitive():
    c = cfg(candidate_genres=["crime"])
    assert c.is_candidate(movie(genres=["Crime"])) is True


def test_exclude_genres_gate():
    c = cfg(candidate_exclude_genres=["Documentary"])
    assert c.is_candidate(movie(genres=["Documentary", "Crime"])) is False
    assert c.is_candidate(movie(genres=["Crime"])) is True


def test_year_range_gate():
    c = cfg(candidate_year_min=1960, candidate_year_max=1979)
    assert c.is_candidate(movie(year=1970)) is True
    assert c.is_candidate(movie(year=1959)) is False
    assert c.is_candidate(movie(year=1980)) is False


def test_fails_open_on_missing_data():
    """A gate never excludes a movie missing the data it gates on."""
    c = cfg(candidate_genres=["Crime"], candidate_year_min=1960)
    # No genres -> genre gate passes (year present and in range).
    assert c.is_candidate(movie(genres=[], year=1970)) is True
    # No year -> year gate passes (genre present and matches).
    assert c.is_candidate(Movie(id=1, title="M", genres=["Crime"], year=None)) is True


def test_from_dict_parses_comma_strings_and_ints():
    """The block delivers values as comma-separated strings; from_dict splits them."""
    c = CollectionConfig.from_dict("Heist Movies", {
        "enabled": True,
        "prompt": "criteria",
        "candidate_genres": "Crime, Thriller, Action",
        "candidate_exclude_genres": "Documentary",
        "candidate_year_min": "1950",
        "candidate_year_max": "2020",
    })
    assert c.candidate_genres == ["Crime", "Thriller", "Action"]
    assert c.candidate_exclude_genres == ["Documentary"]
    assert c.candidate_year_min == 1950
    assert c.candidate_year_max == 2020


def test_from_dict_defaults_empty_when_unset():
    c = CollectionConfig.from_dict("X", {"enabled": True, "prompt": "p"})
    assert c.candidate_genres == []
    assert c.candidate_exclude_genres == []
    assert c.candidate_year_min is None
    assert c.candidate_year_max is None
    assert c.is_candidate(movie(genres=["Anything"], year=1900)) is True
