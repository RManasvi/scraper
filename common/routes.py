"""
common/routes.py — shared city/IATA mappings and priority route list.

All three scrapers target the same 24 routes.  A single source of truth
here means a route added once appears in every airline's scrape run.
"""

CITY_TO_IATA: dict[str, str] = {
    "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "HYDERABAD": "HYD",
    "KOLKATA": "CCU", "PUNE": "PNQ", "GOA": "GOX", "AHMEDABAD": "AMD",
    "CHENNAI": "MAA", "SRINAGAR": "SXR", "GUWAHATI": "GAU", "PATNA": "PAT",
    "LUCKNOW": "LKO", "KOCHI": "COK",
}

# (origin_city, destination_city, total_passengers)
# total_passengers is retained for traceability/QA in output, not used in
# scraping logic itself.
PRIORITY_ROUTES: list[tuple[str, str, int]] = [
    ("DELHI", "MUMBAI", 4029444),
    ("BENGALURU", "DELHI", 2885936),
    ("BENGALURU", "MUMBAI", 2476421),
    ("DELHI", "HYDERABAD", 1862287),
    ("DELHI", "KOLKATA", 1778985),
    ("DELHI", "PUNE", 1704284),
    ("GOA", "MUMBAI", 1495328),
    ("AHMEDABAD", "DELHI", 1402813),
    ("DELHI", "GOA", 1352032),
    ("CHENNAI", "MUMBAI", 1312448),
    ("HYDERABAD", "MUMBAI", 1285881),
    ("KOLKATA", "MUMBAI", 1281897),
    ("CHENNAI", "DELHI", 1277274),
    ("BENGALURU", "HYDERABAD", 1217734),
    ("AHMEDABAD", "MUMBAI", 1215086),
    ("BENGALURU", "KOLKATA", 1204113),
    ("DELHI", "SRINAGAR", 1141145),
    ("BENGALURU", "PUNE", 1079353),
    ("DELHI", "GUWAHATI", 938099),
    ("DELHI", "PATNA", 908354),
    ("BENGALURU", "GOA", 875214),
    ("BENGALURU", "CHENNAI", 872523),
    ("DELHI", "LUCKNOW", 854555),
    ("KOCHI", "MUMBAI", 805813),
]
