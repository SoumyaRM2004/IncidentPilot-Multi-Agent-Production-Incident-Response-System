"""Shared utilities for the IncidentPilot application."""

from datetime import datetime, timezone
from typing import Optional, Union


def normalize_timestamp(ts: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """Convert an ISO-8601 string or datetime to a timezone-aware UTC datetime.

    Handles three input forms:
      - None         → returns None
      - str          → parses ISO-8601 (supports trailing 'Z')
      - datetime     → attaches UTC if naive, converts if aware

    Raises:
        ValueError: If ts is not None, str, or datetime.
    """
    if ts is None:
        return None

    if isinstance(ts, str):
        iso_str = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
        dt = datetime.fromisoformat(iso_str)
    elif isinstance(ts, datetime):
        dt = ts
    else:
        raise ValueError(f"Unsupported timestamp type: {type(ts)}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
