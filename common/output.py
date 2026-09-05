"""
common/output.py — shared timestamped JSON output writer.

Provides a consistent file-naming scheme and JSON structure across all
three airline scrapers so downstream code can treat their outputs uniformly.

Usage:
    from common.output import write_output
    out_path = write_output(
        airline_slug="akasaair",
        output_dir=OUTPUT_DIR,
        records=normalized_all,
        meta={"airline": "Akasa Air", "advance_windows": ADVANCE_WINDOWS},
    )
    print(f"Written to {out_path}")
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def write_output(
    airline_slug: str,
    output_dir: Path,
    records: list[dict],
    meta: Optional[dict] = None,
) -> Path:
    """Write a timestamped JSON file to output_dir and return its path.

    The output envelope always contains:
        - Every key from ``meta`` (caller-supplied, airline-specific)
        - ``last_checked``: UTC ISO-8601 timestamp of this write
        - ``record_count``: number of records
        - ``routes``: the list of normalized records

    Args:
        airline_slug:  Short identifier used in the filename, e.g. "akasaair".
        output_dir:    Directory to write into (must already exist).
        records:       List of normalized record dicts.
        meta:          Extra top-level keys to include in the envelope
                       (e.g. airline name, advance windows, base URL).

    Returns:
        Path of the written file.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = output_dir / f"{airline_slug}_top_24_routes_{stamp}.json"

    envelope: dict = dict(meta or {})
    envelope["last_checked"] = (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    envelope["record_count"] = len(records)
    envelope["routes"] = records

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2, ensure_ascii=False)

    return out_path
