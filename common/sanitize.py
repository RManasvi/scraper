"""
common/sanitize.py — unified null-field sanitizer for scraped records.

Canonical version extracted from spicejet.py.  akasaair.py and airindiaexp.py
do not currently call sanitize_record() — this is intentional.  The function
is available for them to use in future without duplicating the definition.

Usage:
    from common.sanitize import sanitize_record
    clean_records = [sanitize_record(r) for r in raw_records]
"""

# Fields that should default to 0 when null.
NUMERIC_FIELDS: frozenset[str] = frozenset({
    "total_passengers", "advance_purchase_days", "passenger_count",
    "stops", "duration_minutes", "base_fare", "taxes",
    "mandatory_fees", "total_fare", "seats_available",
    "data_quality_score", "discount_amount", "discount_percent",
    "initial_price",
})

# Fields that should default to "N/A" when null.
STRING_FIELDS: frozenset[str] = frozenset({
    "route_id", "origin", "destination", "travel_date", "trip_type",
    "cabin", "airline_code", "airline_name", "flight_number",
    "departure_time", "arrival_time", "fare_family", "currency",
    "availability_status", "source", "source_type", "scrape_outcome",
})

# Fields that should default to False when null.
BOOL_FIELDS: frozenset[str] = frozenset({"no_flights", "sold_out"})


def sanitize_record(record: dict) -> dict:
    """Replace every null with a type-appropriate default.

    data_quality_score stays the real signal for 'is this row trustworthy' —
    do not average total_fare across rows without filtering on that first.

    Unknown fields (not in any of the sets above) also default to "N/A"
    rather than being left as null, matching the original spicejet behavior.
    """
    clean = dict(record)
    for key, value in clean.items():
        if value is not None:
            continue
        if key in NUMERIC_FIELDS:
            clean[key] = 0
        elif key in BOOL_FIELDS:
            clean[key] = False
        else:
            # Covers STRING_FIELDS and any unknown fields
            clean[key] = "N/A"
    if "scrape_outcome" not in clean:
        clean["scrape_outcome"] = "ok"
    return clean
