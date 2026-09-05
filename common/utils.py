"""
common/utils.py — shared utility functions for airline scrapers.

Usage:
    from common.utils import elapsed_minutes
"""

from datetime import datetime
from typing import Optional


def elapsed_minutes(departure: object, arrival: object) -> Optional[int]:
    """Return flight duration in minutes from two ISO-8601 timestamp strings.

    Handles both offset-aware strings (with +05:30 / Z) and naive strings.
    The ``Z`` suffix is normalised to ``+00:00`` before parsing so both
    akasaair.py and spicejet.py edge-cases are covered.

    Returns None if either value is missing or cannot be parsed.
    """
    try:
        dep_str = str(departure).replace("Z", "+00:00")
        arr_str = str(arrival).replace("Z", "+00:00")
        start = datetime.fromisoformat(dep_str)
        end = datetime.fromisoformat(arr_str)
        return int((end - start).total_seconds() // 60)
    except (TypeError, ValueError, AttributeError):
        return None
