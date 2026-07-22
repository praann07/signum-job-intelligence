"""Unit tests for skill extraction (no DB or Redis needed)."""

from app.infrastructure.extraction.extractor import discover_emerging, extract_known

_EMPTY_NORM: dict[str, str] = {}
_EMPTY_ALIAS: dict[str, set[str]] = {}


def test_extract_known_empty_text():
    result = extract_known("", _EMPTY_NORM, _EMPTY_ALIAS)
    assert result == []


def test_extract_known_no_match():
    result = extract_known("we need a good coder", _EMPTY_NORM, _EMPTY_ALIAS)
    assert result == []


def test_discover_emerging_empty():
    result = discover_emerging("", _EMPTY_NORM)
    assert result == []


def test_discover_emerging_noise_only():
    result = discover_emerging("we need a person for the team role year experience", _EMPTY_NORM)
    assert result == []
