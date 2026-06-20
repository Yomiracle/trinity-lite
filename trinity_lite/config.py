"""Configuration normalization helpers."""

from __future__ import annotations

from typing import Any


def string_list(value: Any) -> list[str]:
    """Return a string list from a string, list, or absent value."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"expected string or list of strings, got {type(value).__name__}")
