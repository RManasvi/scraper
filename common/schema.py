"""
common/schema.py — unified output record schema for all airline scrapers.

Defines the canonical superset of fields that can appear in any scraper's
output.  Use this for downstream merging, DataFrame construction, or CSV
export so all three airlines' records can be treated uniformly.

Usage:
    from common.schema import RECORD_FIELDS, make_empty_record
    df = pd.DataFrame(records, columns=list(RECORD_FIELDS.keys()))
"""

from collections import OrderedDict

# Field name → default value (used when a record does not include that field).
# Fields are ordered: identifiers → route info → flight info → pricing → meta.
RECORD_FIELDS: OrderedDict[str, object] = OrderedDict([
    # --- Identifiers ---
    ("observation_id",          None),
    ("collection_timestamp",    None),

    # --- Route ---
    ("route_id",                "N/A"),
    ("total_passengers",        0),
    ("origin",                  "N/A"),
    ("destination",             "N/A"),
    ("travel_date",             "N/A"),
    ("advance_purchase_days",   0),
    ("trip_type",               "one_way"),
    ("passenger_count",         1),
    ("cabin",                   "economy"),

    # --- Flight ---
    ("stops",                   None),
    ("airline_code",            "N/A"),
    ("airline_name",            "N/A"),
    ("flight_number",           None),
    ("departure_time",          None),
    ("arrival_time",            None),
    ("duration_minutes",        None),

    # --- Pricing ---
    ("fare_family",             None),
    ("base_fare",               None),
    ("taxes",                   None),
    ("mandatory_fees",          None),
    ("total_fare",              None),
    ("currency",                "INR"),

    # --- Availability ---
    ("availability_status",     "N/A"),
    ("seats_available",         None),
    ("no_flights",              None),
    ("sold_out",                None),

    # --- Source / Quality ---
    ("source",                  "N/A"),
    ("source_type",             "N/A"),
    ("data_quality_score",      0),
    ("scrape_outcome",          "ok"),

    # --- AirIndiaExpress-specific (None for other airlines) ---
    ("source_url",              None),
    ("note",                    None),
])


def make_empty_record() -> dict:
    """Return a dict with all schema fields set to their defaults."""
    return dict(RECORD_FIELDS)


def normalize_to_schema(record: dict) -> dict:
    """Fill any missing schema fields with defaults, drop no existing keys.

    Does not remove extra keys a scraper may have added.
    """
    base = make_empty_record()
    base.update(record)
    return base
