"""Yatra published-fare collector for the VAYUSETU route basket.

This collector intentionally reads only Yatra's public ``/flight-schedule/``
route pages. It does not call or replay private booking APIs, use stealth,
solve CAPTCHAs, or circumvent a block. The public page currently publishes a
seven-day lowest-fare calendar and may render flight cards for one travel date.
Unavailable advance windows are preserved as explicit ``not_published`` rows.

Fully self-contained — no common/ imports required.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Browser, Page, async_playwright

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]
RATE_LIMIT_SECONDS = 5

BASE_URL = "https://www.yatra.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
USER_AGENT = "VAYUSETU-ResearchBot/1.0"

OUTPUT_DIR = Path(__file__).parent / "yatra"
OUTPUT_DIR.mkdir(exist_ok=True)
SS_DIR = OUTPUT_DIR / "ss"
SS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# HARDCODED ROUTES  (origin_city, dest_city, origin_iata, dest_iata, pax)
# Same 24 routes and passenger figures used by akasaair.py / spicejet.py.
# ---------------------------------------------------------------------------
PRIORITY_ROUTES: list[tuple[str, str, str, str, int]] = [
    ("DELHI",     "MUMBAI",    "DEL", "BOM", 4029444),
    ("BENGALURU", "DELHI",     "BLR", "DEL", 2885936),
    ("BENGALURU", "MUMBAI",    "BLR", "BOM", 2476421),
    ("DELHI",     "HYDERABAD", "DEL", "HYD", 1862287),
    ("DELHI",     "KOLKATA",   "DEL", "CCU", 1778985),
    ("DELHI",     "PUNE",      "DEL", "PNQ", 1704284),
    ("GOA",       "MUMBAI",    "GOX", "BOM", 1495328),
    ("AHMEDABAD", "DELHI",     "AMD", "DEL", 1402813),
    ("DELHI",     "GOA",       "DEL", "GOX", 1352032),
    ("CHENNAI",   "MUMBAI",    "MAA", "BOM", 1312448),
    ("HYDERABAD", "MUMBAI",    "HYD", "BOM", 1285881),
    ("KOLKATA",   "MUMBAI",    "CCU", "BOM", 1281897),
    ("CHENNAI",   "DELHI",     "MAA", "DEL", 1277274),
    ("BENGALURU", "HYDERABAD", "BLR", "HYD", 1217734),
    ("AHMEDABAD", "MUMBAI",    "AMD", "BOM", 1215086),
    ("BENGALURU", "KOLKATA",   "BLR", "CCU", 1204113),
    ("DELHI",     "SRINAGAR",  "DEL", "SXR", 1141145),
    ("BENGALURU", "PUNE",      "BLR", "PNQ", 1079353),
    ("DELHI",     "GUWAHATI",  "DEL", "GAU",  938099),
    ("DELHI",     "PATNA",     "DEL", "PAT",  908354),
    ("BENGALURU", "GOA",       "BLR", "GOX",  875214),
    ("BENGALURU", "CHENNAI",   "BLR", "MAA",  872523),
    ("DELHI",     "LUCKNOW",   "DEL", "LKO",  854555),
    ("KOCHI",     "MUMBAI",    "COK", "BOM",  805813),
]

# ---------------------------------------------------------------------------
# HARDCODED YATRA ROBOTS RULES
# Source: https://www.yatra.com/robots.txt  (reviewed 2026-08-28)
# Hardcoded to eliminate CI network-fetch timeouts.
# /flight-schedule/ is NOT in any Disallow rule → always allowed.
# ---------------------------------------------------------------------------
_YATRA_ROBOTS_TEXT = """\
User-agent: *
Allow: /
Disallow: /FM/
Disallow: /TP/
Disallow: /SIFY/
Disallow: /ZEE/
Disallow: /TUI/
Disallow: /DH/
Disallow: /HT/
Disallow: /HUGYATRA/
Disallow: /AGS/
Disallow: /AG/
Disallow: /AFFILIATE/
Disallow: /JT/
Disallow: /ITZFLY/
Disallow: /AOL/
Disallow: /international/AOL/
Disallow: /ads/
Disallow: /c/journal/
Disallow: /h/components/
Disallow: /content/useralbums/
Disallow: /YT/YT_common/
Disallow: /fresco/
Disallow: /pwa/
Disallow: /pwa
Disallow: /cars.html
Disallow: /buses.html
Disallow: /index2.html
Disallow: /hotels-india-v2/
Disallow: /flights-india-vx/
Disallow: /holiday-v2/
Disallow: /spice-jet-offer.html
Disallow: /hotels-india/hotel/home.htm
Disallow: /flights-india-yt/aff/
Disallow: /hotels/affiliateConfirmer.htm
Disallow: /destinations/in/
Disallow: /offer/content/images
Disallow: /monuments/
Disallow: /yatra-seo/hotel-detail-content
Disallow: /international/US/india/
Disallow: /international/YT/
Disallow: /international/air-tickets/
Disallow: /international/cheap-tickets/
Disallow: /international/cheap-airfare/
Disallow: /international/cheap-airline-tickets/
Disallow: /international/airlines/
Disallow: /international/air-fares/
Disallow: /international/airfare/
Disallow: /trains-new.html
Disallow: /hotels-beta/
Disallow: /hotels-india/hotel/
Disallow: /travel-beta/cheap-air-tickets
Sitemap: https://www.yatra.com/sitemap/flight-schedule.xml
"""
_YATRA_ROBOTS_LINES: list[str] = _YATRA_ROBOTS_TEXT.splitlines()

# ---------------------------------------------------------------------------
# LOCAL OUTPUT WRITER  (mirrors common/output.py write_output)
# ---------------------------------------------------------------------------

def write_output(records: list[dict]) -> Path:
    """Write a timestamped JSON envelope to OUTPUT_DIR and return its path."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"yatra_top_24_routes_{stamp}.json"
    envelope = {
        "platform": "Yatra",
        "base_url": BASE_URL,
        "robots_url": ROBOTS_URL,
        "collection_surface": "/flight-schedule/ public route pages only",
        "user_agent": USER_AGENT,
        "rate_limit_seconds": RATE_LIMIT_SECONDS,
        "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "advance_windows": ADVANCE_WINDOWS,
        "record_count": len(records),
        "routes": records,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2, ensure_ascii=False)
    return out_path

CITY_SLUGS = {
    "DELHI": "delhi",
    "MUMBAI": "mumbai",
    "BENGALURU": "bangalore",
    "HYDERABAD": "hyderabad",
    "KOLKATA": "kolkata",
    "PUNE": "pune",
    "GOA": "goa",
    "AHMEDABAD": "ahmedabad",
    "CHENNAI": "chennai",
    "SRINAGAR": "srinagar",
    "GUWAHATI": "guwahati",
    "PATNA": "patna",
    "LUCKNOW": "lucknow",
    "KOCHI": "kochi",
}

AIRLINE_CODES = {
    "6E": "IndiGo",
    "AI": "Air India",
    "IX": "Air India Express",
    "QP": "Akasa Air",
    "SG": "SpiceJet",
    "S5": "Star Air",
}


def robots_policy_allows(lines: list[str], url: str) -> bool:
    """Apply RFC-style longest-match rules from Yatra's ``User-agent: *`` group."""
    rules: list[tuple[bool, str]] = []
    in_star_group = False
    for raw_line in lines:
        line = raw_line.partition("#")[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if in_star_group and value != "*":
                break
            in_star_group = value == "*"
        elif in_star_group and field in {"allow", "disallow"} and value:
            rules.append((field == "allow", value))

    target = urlsplit(url)
    path = target.path + (f"?{target.query}" if target.query else "")
    matches: list[tuple[int, bool]] = []
    for allowed, pattern in rules:
        anchored = pattern.endswith("$")
        raw_pattern = pattern[:-1] if anchored else pattern
        expression = re.escape(raw_pattern).replace(r"\*", ".*")
        expression = f"^{expression}{'$' if anchored else ''}"
        if re.search(expression, path):
            specificity = len(raw_pattern.replace("*", ""))
            matches.append((specificity, allowed))
    if not matches:
        return True
    longest = max(specificity for specificity, _ in matches)
    return any(allowed for specificity, allowed in matches if specificity == longest)


def robots_allowed(url: str) -> bool:
    """Check URL against hardcoded Yatra robots rules (no network fetch)."""
    return robots_policy_allows(_YATRA_ROBOTS_LINES, url)


def route_url(origin_city: str, destination_city: str) -> str:
    origin = CITY_SLUGS[origin_city]
    destination = CITY_SLUGS[destination_city]
    return f"{BASE_URL}/flight-schedule/{origin}-to-{destination}-flights.html"


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.replace("\u00a0", " ").splitlines() if line.strip()]


def _nearest_year(month: int, day: int, reference: date) -> int:
    candidates = [date(reference.year + offset, month, day) for offset in (-1, 0, 1)]
    return min(candidates, key=lambda candidate: abs((candidate - reference).days)).year


def _parse_page_date(lines: list[str], reference: date) -> date | None:
    pattern = re.compile(r"^[A-Z][a-z]{2},\s+(\d{1,2})\s+([A-Z][a-z]{2})'(\d{2})$")
    for line in lines[:80]:
        match = pattern.match(line)
        if match:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)}", "%d %b %y"
            ).date()
    return None


def parse_fare_calendar(text: str, reference: date | None = None) -> dict[str, float]:
    reference = reference or date.today()
    fares: dict[str, float] = {}
    combined_pattern = re.compile(
        r"^[A-Z][a-z]{2},\s+(\d{1,2})\s+([A-Z][a-z]{2})\s*₹\s*([\d,]+)$"
    )
    split_pattern = re.compile(r"^[A-Z][a-z]{2},\s+(\d{1,2})\s+([A-Z][a-z]{2})$")
    lines = _lines(text)
    for index, line in enumerate(lines):
        match = combined_pattern.match(line)
        amount = match.group(3) if match else None
        if not match:
            match = split_pattern.match(line)
            if match and index + 1 < len(lines):
                price_match = re.fullmatch(r"₹\s*([\d,]+)", lines[index + 1])
                amount = price_match.group(1) if price_match else None
        if not match or not amount:
            continue
        parsed = datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d %b")
        year = _nearest_year(parsed.month, parsed.day, reference)
        travel_date = date(year, parsed.month, parsed.day).isoformat()
        fares[travel_date] = float(amount.replace(",", ""))
    return fares


def parse_date_picker_calendar(text: str) -> dict[str, float]:
    """Parse the month grids exposed by Yatra's public departure-date picker."""
    lines = _lines(text)
    fares: dict[str, float] = {}
    month_headers: list[tuple[int, int]] = []
    grid_index = -1
    month = None
    year = None
    in_picker = False
    for index, line in enumerate(lines):
        month_match = re.fullmatch(r"([A-Z][a-z]+)\s+(20\d{2})", line)
        if month_match:
            try:
                parsed_month = datetime.strptime(month_match.group(1), "%B").month
            except ValueError:
                continue
            month_headers.append((int(month_match.group(2)), parsed_month))
            in_picker = True
            continue
        if in_picker and line == "Return":
            break
        if in_picker and line == "Mo":
            grid_index += 1
            if grid_index < len(month_headers):
                year, month = month_headers[grid_index]
            continue
        if not in_picker or month is None or year is None:
            continue
        if re.fullmatch(r"\d{1,2}", line) and index + 1 < len(lines):
            day = int(line)
            price_match = re.fullmatch(r"₹\s*([\d,]+)", lines[index + 1])
            if not price_match:
                continue
            try:
                travel_date = date(year, month, day).isoformat()
            except ValueError:
                continue
            fares[travel_date] = float(price_match.group(1).replace(",", ""))
    return fares


def _duration_and_stops(value: str) -> tuple[int | None, int | None]:
    duration = re.search(r"(?:(\d+)h)?\s*(?:(\d+)m)?", value)
    minutes = None
    if duration and any(duration.groups()):
        minutes = int(duration.group(1) or 0) * 60 + int(duration.group(2) or 0)
    lowered = value.lower()
    if "direct" in lowered or "non-stop" in lowered or "non stop" in lowered:
        stops = 0
    else:
        stop_match = re.search(r"(\d+)\s*stop", lowered)
        stops = int(stop_match.group(1)) if stop_match else None
    return minutes, stops


def _card_date(value: str, reference: date) -> str | None:
    try:
        parsed = datetime.strptime(value, "%b %d")
    except ValueError:
        return None
    year = _nearest_year(parsed.month, parsed.day, reference)
    return date(year, parsed.month, parsed.day).isoformat()


def parse_flight_cards(
    text: str,
    expected_origin: str,
    expected_destination: str,
    reference: date | None = None,
) -> list[dict]:
    """Parse the stable text labels in Yatra's public flight cards."""
    reference = reference or date.today()
    lines = _lines(text)
    cards: list[dict] = []
    for index, line in enumerate(lines):
        if line.lower() != "total fare" or index < 8:
            continue
        before = lines[max(0, index - 24):index]
        after = lines[index + 1:index + 6]
        try:
            code_at = next(
                i for i, value in enumerate(before)
                if re.fullmatch(r"[A-Z0-9]{2}", value)
            )
            origin_at = next(
                i for i in range(code_at + 1, len(before))
                if before[i] == f"({expected_origin})" or before[i].endswith(f"({expected_origin})")
            )
            destination_at = next(
                i for i in range(origin_at + 1, len(before))
                if before[i] == f"({expected_destination})" or before[i].endswith(f"({expected_destination})")
            )
            departure_at = max(
                i for i in range(code_at + 1, origin_at) if re.fullmatch(r"\d{2}:\d{2}", before[i])
            )
            arrival_at = max(
                i for i in range(origin_at + 1, destination_at) if re.fullmatch(r"\d{2}:\d{2}", before[i])
            )
            duration_at = next(
                i for i in range(origin_at + 1, arrival_at)
                if re.search(r"\d+h", before[i], re.IGNORECASE)
            )
        except (StopIteration, ValueError):
            continue

        fare = None
        for fare_at, value in enumerate(after):
            combined_fare = re.fullmatch(r"₹\s*([\d,]+)", value)
            plain_fare = re.fullmatch(r"[\d,]+", value)
            if combined_fare:
                fare = float(combined_fare.group(1).replace(",", ""))
                break
            if plain_fare and fare_at > 0 and after[fare_at - 1] == "₹":
                fare = float(value.replace(",", ""))
                break
        if fare is None:
            continue

        departure_date = next(
            (
                parsed
                for value in before[origin_at + 1:duration_at]
                if (parsed := _card_date(value, reference))
            ),
            None,
        )
        arrival_date = next(
            (
                parsed
                for value in before[destination_at + 1:]
                if (parsed := _card_date(value, reference))
            ),
            departure_date,
        )
        if not departure_date:
            continue
        departure_datetime = datetime.fromisoformat(
            f"{departure_date}T{before[departure_at]}:00"
        )
        arrival_datetime = datetime.fromisoformat(
            f"{arrival_date or departure_date}T{before[arrival_at]}:00"
        )
        if arrival_datetime <= departure_datetime:
            arrival_datetime += timedelta(days=1)
        duration_minutes, stops = _duration_and_stops(" ".join(before[duration_at:arrival_at]))
        airline_code = before[code_at]
        airline_name = before[code_at - 1] if code_at else AIRLINE_CODES.get(airline_code)
        cards.append({
            "airline_code": airline_code,
            "airline_name": AIRLINE_CODES.get(airline_code, airline_name),
            "flight_number": None,
            "departure_time": departure_datetime.isoformat(timespec="seconds"),
            "arrival_time": arrival_datetime.isoformat(timespec="seconds"),
            "travel_date": departure_date,
            "duration_minutes": duration_minutes,
            "stops": stops,
            "total_fare": fare,
        })
    return cards


def parse_structured_flights(
    scripts: list[str],
    expected_origin: str,
    expected_destination: str,
) -> list[dict]:
    """Read exact flight identifiers from public Schema.org Flight records."""
    flights: list[dict] = []
    india_timezone = timezone(timedelta(hours=5, minutes=30))

    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            if value.get("@type") == "Flight":
                yield value
            for item in value.values():
                yield from walk(item)

    def iata_code(value) -> str | None:
        if isinstance(value, str):
            return value.upper()
        if isinstance(value, list):
            return next((item.upper() for item in value if isinstance(item, str)), None)
        return None

    def local_time(value) -> str | None:
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(india_timezone).replace(tzinfo=None)
        return parsed.isoformat(timespec="seconds")

    for script in scripts:
        try:
            document = json.loads(script)
        except (json.JSONDecodeError, TypeError):
            continue
        for flight in walk(document):
            departure_airport = flight.get("departureAirport") or {}
            arrival_airport = flight.get("arrivalAirport") or {}
            if (
                iata_code(departure_airport.get("iataCode")) != expected_origin
                or iata_code(arrival_airport.get("iataCode")) != expected_destination
            ):
                continue

            raw_number = flight.get("flightNumber")
            if not isinstance(raw_number, str):
                continue
            numbers = re.findall(r"\b[A-Z0-9]{2}\s*-?\s*\d{1,4}\b", raw_number.upper())
            numbers = [re.sub(r"\s|-", "", number) for number in numbers]
            numbers = list(dict.fromkeys(numbers))
            if not numbers:
                continue

            provider = flight.get("provider") or {}
            provider_code = iata_code(provider.get("iataCode"))
            airline_code = provider_code or re.match(r"[A-Z0-9]{2}", numbers[0]).group(0)
            departure_time = local_time(flight.get("departureTime"))
            arrival_time = local_time(flight.get("arrivalTime"))
            if departure_time and arrival_time:
                departure_datetime = datetime.fromisoformat(departure_time)
                arrival_datetime = datetime.fromisoformat(arrival_time)
                if arrival_datetime <= departure_datetime:
                    arrival_time = (arrival_datetime + timedelta(days=1)).isoformat(
                        timespec="seconds"
                    )
            flights.append({
                "airline_code": airline_code,
                "flight_number": ",".join(numbers),
                "departure_time": departure_time,
                "arrival_time": arrival_time,
            })
    return flights


def attach_flight_numbers(cards: list[dict], structured_flights: list[dict]) -> None:
    """Attach a number only when public structured data gives one exact match."""
    for card in cards:
        candidates = [
            flight for flight in structured_flights
            if flight.get("airline_code") == card.get("airline_code")
            and flight.get("departure_time") == card.get("departure_time")
            and flight.get("arrival_time") == card.get("arrival_time")
        ]
        if len(candidates) == 1:
            card["flight_number"] = candidates[0]["flight_number"]


def normalized_record(
    route: tuple,
    travel_date: str,
    advance_days: int,
    source_url: str,
    offer: dict | None = None,
    calendar_fare: float | None = None,
    outcome: str = "published_fare",
) -> dict:
    origin_city, destination_city, origin, destination, passengers = route
    offer = offer or {}
    total_fare = offer.get("total_fare", calendar_fare)
    available = total_fare is not None
    return {
        "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
        "collection_timestamp": datetime.now().astimezone().isoformat(),
        "route_id": f"{origin_city}-{destination_city}",
        "total_passengers": passengers,
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "advance_purchase_days": advance_days,
        "trip_type": "one_way",
        "passenger_count": 1,
        "cabin": "economy",
        "stops": offer.get("stops"),
        "airline_code": offer.get("airline_code"),
        "airline_name": offer.get("airline_name"),
        "flight_number": offer.get("flight_number"),
        "departure_time": offer.get("departure_time"),
        "arrival_time": offer.get("arrival_time"),
        "duration_minutes": offer.get("duration_minutes"),
        "fare_family": "Economy" if available else None,
        "base_fare": None,
        "taxes": None,
        "mandatory_fees": None,
        "fare_components_available": False,
        "fare_components_note": "Yatra public route page publishes total fare only",
        "total_fare": total_fare,
        "currency": "INR",
        "availability_status": "available" if available else "not_published",
        "seats_available": None,
        "source": "Yatra",
        "source_type": "ota_published_fare_page",
        "data_quality_score": 85 if offer and available else (60 if available else 0),
        "no_flights": None,
        "sold_out": None,
        "source_url": source_url,
        "seller_name": "Yatra",
        "scrape_outcome": outcome,
    }


async def collect_route(page: Page, route: tuple, today: date) -> list[dict]:
    origin_city, destination_city, origin, destination, _ = route
    url = route_url(origin_city, destination_city)
    if not robots_allowed(url):
        return [
            normalized_record(
                route,
                (today + timedelta(days=days)).isoformat(),
                days,
                url,
                outcome="robots_disallowed",
            )
            for days in ADVANCE_WINDOWS
        ]

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        if not response or response.status != 200:
            raise RuntimeError(f"http_{response.status if response else 'none'}")
        await page.wait_for_timeout(3_000)
        body = await page.locator("body").inner_text()
        structured_scripts = await page.locator(
            "script[type='application/ld+json']"
        ).all_text_contents()
    except Exception as exc:
        print(f"  [!] {origin}-{destination}: {exc}")
        return [
            normalized_record(
                route,
                (today + timedelta(days=days)).isoformat(),
                days,
                url,
                outcome="connection_blocked",
            )
            for days in ADVANCE_WINDOWS
        ]

    lines = _lines(body)
    page_date = _parse_page_date(lines, today) or today
    fares = parse_fare_calendar(body, page_date)
    cards = parse_flight_cards(body, origin, destination, page_date)
    structured_flights = parse_structured_flights(
        structured_scripts, origin, destination
    )
    attach_flight_numbers(cards, structured_flights)
    target_dates = {
        (today + timedelta(days=days)).isoformat() for days in ADVANCE_WINDOWS
    }

    departure_label = f"{page_date:%a}, {page_date.day} {page_date:%b}'{page_date:%y}"
    departure_controls = page.get_by_text(departure_label, exact=True)
    picker_opened = False
    for index in range(await departure_controls.count()):
        candidate = departure_controls.nth(index)
        if await candidate.is_visible():
            await candidate.click()
            await page.wait_for_timeout(400)
            picker_opened = True
            break
    if picker_opened:
        next_month = page.get_by_role("button", name="Next month")
        for _ in range(3):
            picker_text = await page.locator("body").inner_text()
            fares.update(parse_date_picker_calendar(picker_text))
            if target_dates.issubset(fares) or not await next_month.count():
                break
            if not await next_month.first.is_enabled():
                break
            await next_month.first.click()
            await page.wait_for_timeout(300)
        await page.keyboard.press("Escape")

    cards_by_date: dict[str, list[dict]] = {}
    for card in cards:
        cards_by_date.setdefault(card["travel_date"], []).append(card)

    records = []
    for days in ADVANCE_WINDOWS:
        travel_date = (today + timedelta(days=days)).isoformat()
        offers = cards_by_date.get(travel_date, [])
        if offers:
            records.extend(
                normalized_record(route, travel_date, days, url, offer=offer)
                for offer in offers
            )
        else:
            fare = fares.get(travel_date)
            records.append(normalized_record(
                route,
                travel_date,
                days,
                url,
                calendar_fare=fare,
                outcome="published_calendar_fare" if fare is not None else "not_published",
            ))
    return records


async def run_batch_scrape(headless: bool = True, test_only: bool = False) -> list[dict]:
    today = date.today()
    routes = PRIORITY_ROUTES[:1] if test_only else PRIORITY_ROUTES
    records: list[dict] = []
    async with async_playwright() as playwright:
        # Yatra's public route pages currently fail in Chromium with
        # net::ERR_HTTP2_PROTOCOL_ERROR (and hang when HTTP/2 is disabled).
        # Firefox loads the same allowed public surface normally, so keep this
        # collector isolated on Firefox while the other collectors use Chromium.
        browser: Browser = await playwright.firefox.launch(headless=headless)
        contact = os.getenv("VAYUSETU_CONTACT_EMAIL", "").strip()
        page = await browser.new_page(
            viewport={"width": 1366, "height": 768},
            extra_http_headers={"From": contact} if contact else None,
        )
        for index, route in enumerate(routes, 1):
            print(f"[{index}/{len(routes)}] {route[2]}-{route[3]}")
            records.extend(await collect_route(page, route, today))
            if index < len(routes):
                await asyncio.sleep(RATE_LIMIT_SECONDS)
        await browser.close()

    if not test_only:
        priced_count = sum(record.get("total_fare") is not None for record in records)
        failure_outcomes = {"connection_blocked", "robots_disallowed"}
        if records and not priced_count and all(
            record.get("scrape_outcome") in failure_outcomes for record in records
        ):
            raise RuntimeError(
                "Yatra collection failed for every route; preserved the previous output and skipped ETL"
            )
        out_path = write_output(records)
        print(f"Wrote {len(records)} records ({priced_count} priced) to {out_path}")
    else:
        outcomes: dict[str, int] = {}
        for record in records:
            outcome = record["scrape_outcome"]
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        print(f"Test records: {len(records)} | outcomes: {outcomes}")
        numbered = sum(record["flight_number"] is not None for record in records)
        print(f"Exact flight numbers matched: {numbered}")
        windows = {}
        for record in records:
            days = record["advance_purchase_days"]
            windows.setdefault(days, {
                "travel_date": record["travel_date"],
                "priced_records": 0,
                "outcome": record["scrape_outcome"],
            })
            if record["total_fare"] is not None:
                windows[days]["priced_records"] += 1
        print(f"Windows: {json.dumps(windows, sort_keys=True)}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Yatra public published-fare collector")
    parser.add_argument("--test", action="store_true", help="collect only DEL-BOM and do not overwrite batch output")
    parser.add_argument("--headed", action="store_true", help="show the browser while collecting")
    args = parser.parse_args()
    asyncio.run(run_batch_scrape(headless=not args.headed, test_only=args.test))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Quick alias: `python yatra.py test` → same as --test
        asyncio.run(run_batch_scrape(headless=True, test_only=True))
    else:
        main()