
import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from common.routes import CITY_TO_IATA, PRIORITY_ROUTES
from common.robots import robots_allowed as _robots_allowed_base
from common.stealth import apply_stealth, LAUNCH_ARGS
from common.utils import elapsed_minutes
from common.output import write_output


# ---------------------------
# CONFIG
# ---------------------------

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

OUTPUT_DIR = Path("akasaair")
OUTPUT_DIR.mkdir(exist_ok=True)
SS_DIR = OUTPUT_DIR / "ss"
SS_DIR.mkdir(exist_ok=True)

USER_AGENT = "VAYUSETU-Bot"

def robots_allowed(url: str) -> bool:
    """Pass VAYUSETU-Bot as user-agent to the common robots checker."""
    return _robots_allowed_base(url, user_agent=USER_AGENT)
# CITY_TO_IATA and PRIORITY_ROUTES imported from common.routes
IATA_TO_SEARCH_NAME = {
    code: city.title() for city, code in CITY_TO_IATA.items()
}

# Akasa-specific: city-to-URL-slug (uses "new-delhi" vs airindiaexp's "delhi")
CITY_TO_SLUG = {
    "DELHI": "new-delhi",
    "MUMBAI": "mumbai",
    "BENGALURU": "bengaluru",
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


def build_routes_from_slugs():
    routes = []
    for o_city, d_city, pax in PRIORITY_ROUTES:
        o_code = CITY_TO_IATA.get(o_city, o_city[:3])
        d_code = CITY_TO_IATA.get(d_city, d_city[:3])
        o_slug = CITY_TO_SLUG.get(o_city, o_city.lower())
        d_slug = CITY_TO_SLUG.get(d_city, d_city.lower())
        route_id = f"{o_city}-{d_city}"
        routes.append((o_code, d_code, o_slug, d_slug, route_id, pax))
    return routes


ROUTES_WITH_SLUGS = build_routes_from_slugs()


# ---------------------------
# CORE SCRAPE FUNCTION
# ---------------------------
async def scrape_route(origin: str, dest: str, travel_date: str,
                        origin_slug: str = None, dest_slug: str = None,
                        headless: bool = True, additional_dates=None):
    """
    Loads Akasa's direct city-to-city page when slugs are available.
    Falls back to homepage + manual field-fill if no slug page exists.
    """
    captured = {"responses": {}}

    def requested_availability_captured():
        response = captured["responses"].get("availability") or {}
        try:
            payload = json.loads(response.get("request_payload") or "{}")
            stations = payload["criteria"][0]["stations"]
            origins = stations.get("originStationCodes") or []
            destinations = stations.get("destinationStationCodes") or []
            begin_date = payload["criteria"][0]["dates"].get("beginDate", "")[:10]
            return origin in origins and dest in destinations and begin_date == travel_date
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return False

    async def handle_response(response):
        path = urlparse(response.url).path.lower()
        is_fare_calendar = "lowfare" in path
        # Akasa has changed the versioned path used for flight results. Match
        # the availability search resource without pinning the scraper to one
        # API version, while keeping lowFare classified as calendar data.
        is_availability = "availability" in path and not is_fare_calendar
        if (is_fare_calendar or is_availability) and response.status == 200:
            try:
                if not robots_allowed(response.url):
                    print(f"  [!] Robots policy disallows API URL: {response.url}")
                    return
                body = await response.json()
                kind = "lowFare" if is_fare_calendar else "availability"
                captured["responses"][kind] = {
                    "url": response.url,
                    "status": response.status,
                    "request_payload": response.request.post_data,
                    "request_headers": response.request.headers,
                    "data": body.get("data", body) if isinstance(body, dict) else body,
                }
            except Exception:
                pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=LAUNCH_ARGS,
        )
        page = await browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
        )
        await apply_stealth(page)

        async def set_requested_date(route, request):
            """Keep Akasa's own browser request, but set the requested window date."""
            try:
                payload = json.loads(request.post_data or "{}")
                for criterion in payload.get("criteria") or []:
                    dates = criterion.setdefault("dates", {})
                    dates["beginDate"] = f"{travel_date}T00:00:00"
                await route.continue_(post_data=json.dumps(payload))
            except (TypeError, ValueError, json.JSONDecodeError):
                await route.continue_()

        await page.route("**/api/ibe/availability/search", set_requested_date)
        page.on("response", handle_response)

        try:
            used_fallback = False
            if origin_slug and dest_slug:
                url = f"https://www.akasaair.com/flight-booking/{origin_slug}-to-{dest_slug}"
                if not robots_allowed(url):
                    print(f"  [!] Robots policy disallows page URL: {url}")
                    return None
                await page.goto(url, wait_until="load", timeout=30000)
                await page.wait_for_timeout(4000)

                try:
                    await page.click("text=Accept cookies", timeout=4000)
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

                try:
                    from_value = await page.locator("#From").input_value(timeout=5000)
                except Exception:
                    from_value = ""

                if not from_value and not requested_availability_captured():
                    print(f"  [!] {origin_slug}-to-{dest_slug} page has no pre-filled From -- falling back to manual fill")
                    used_fallback = True
            else:
                used_fallback = True

            if used_fallback:
                homepage = "https://www.akasaair.com/"
                if not robots_allowed(homepage):
                    print(f"  [!] Robots policy disallows page URL: {homepage}")
                    return None
                await page.goto(homepage, wait_until="load", timeout=30000)
                await page.wait_for_timeout(3000)
                try:
                    await page.click("text=Accept cookies", timeout=4000)
                except Exception:
                    pass

                from_input = page.locator("#From")
                await from_input.click(timeout=10000)
                await from_input.fill("")
                await page.wait_for_timeout(300)
                from_search = IATA_TO_SEARCH_NAME.get(origin, origin)
                await from_input.type(from_search, delay=150)
                await page.wait_for_timeout(1500)
                try:
                    await page.locator(f"#destinations li#{origin}").click(timeout=3000)
                except Exception:
                    try:
                        await page.locator("#destinations li").filter(has_text=from_search).first.click(timeout=3000)
                    except Exception:
                        await page.keyboard.press("ArrowDown")
                        await page.wait_for_timeout(300)
                        await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)

                to_input = page.locator("#To")
                await to_input.click(timeout=10000)
                await to_input.fill("")
                await page.wait_for_timeout(300)
                dest_search = IATA_TO_SEARCH_NAME.get(dest, dest)
                await to_input.type(dest_search, delay=150)
                await page.wait_for_timeout(1500)
                try:
                    await page.locator(f"#destinations li#{dest}").click(timeout=3000)
                except Exception:
                    try:
                        await page.locator("#destinations li").filter(has_text=dest_search).first.click(timeout=3000)
                    except Exception:
                        await page.keyboard.press("ArrowDown")
                        await page.wait_for_timeout(300)
                        await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)

                try:
                    error_visible = await page.locator("text=Please enter a valid airport").is_visible(timeout=1000)
                except Exception:
                    error_visible = False
                if error_visible:
                    print(f"  [!] Airport selection did not register for {origin}->{dest}, skipping")
                    await page.screenshot(path=str(SS_DIR / "last_run_debug.png"), full_page=True)
                    await browser.close()
                    return None

            if not requested_availability_captured():
                try:
                    date_input = page.locator("input[name='DepartureDate']")
                    await date_input.fill(travel_date, timeout=5000)
                    await date_input.press("Tab")
                    await page.wait_for_timeout(1200)
                except Exception as e:
                    print(f"  [!] Could not set departure date: {e}")

                for sel in [
                    "button:has-text('Search Flights')",
                    "button:has-text('Search')",
                    "button[type='submit']",
                ]:
                    try:
                        await page.click(sel, timeout=2500)
                        break
                    except Exception:
                        continue

                await page.wait_for_timeout(10000)

        except Exception as e:
            print(f"  [!] Error during navigation for {origin}->{dest} on {travel_date}: {e}")

        if additional_dates and requested_availability_captured():
            initial = captured["responses"]["availability"]
            captured["window_responses"] = {
                travel_date: {"responses": {"availability": initial}}
            }
            request_url = initial["url"]
            template = json.loads(initial.get("request_payload") or "{}")
            allowed_headers = {
                key: value for key, value in (initial.get("request_headers") or {}).items()
                if key.lower() in {"accept", "authorization", "content-type", "origin", "referer", "user-agent"}
            }
            for requested_date in additional_dates:
                if not robots_allowed(request_url):
                    print(f"  [!] Robots policy disallows API URL: {request_url}")
                    continue
                payload = json.loads(json.dumps(template))
                for criterion in payload.get("criteria") or []:
                    criterion.setdefault("dates", {})["beginDate"] = f"{requested_date}T00:00:00"
                await asyncio.sleep(3)
                api_response = await page.request.post(
                    request_url,
                    headers=allowed_headers,
                    data=payload,
                    timeout=30000,
                )
                if api_response.status != 200:
                    print(f"  [!] Availability returned HTTP {api_response.status} for {requested_date}")
                    continue
                body = await api_response.json()
                captured["window_responses"][requested_date] = {
                    "responses": {
                        "availability": {
                            "url": request_url,
                            "status": api_response.status,
                            "data": body.get("data", body) if isinstance(body, dict) else body,
                        }
                    }
                }

        if not requested_availability_captured():
            try:
                await page.screenshot(path=str(SS_DIR / "last_run_debug.png"), full_page=True)
            except Exception:
                pass

        await browser.close()

    return captured if captured["responses"] else None


# ---------------------------
# NORMALIZATION
# ---------------------------
def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def first_value(value, keys):
    for item in iter_dicts(value):
        for key in keys:
            if item.get(key) is not None:
                return item[key]
    return None


def duration_minutes(value):
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return None
    parts = value.lower().replace(" ", "").split("h")
    try:
        hours = int(parts[0])
        minutes = int(parts[1].split("m")[0]) if len(parts) > 1 and parts[1] else 0
        return hours * 60 + minutes
    except (ValueError, IndexError):
        return None


def elapsed_minutes(departure, arrival):
    """Return elapsed minutes for Akasa's ISO-8601 designator timestamps."""
    try:
        start = datetime.fromisoformat(str(departure).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(arrival).replace("Z", "+00:00"))
        return int((end - start).total_seconds() // 60)
    except (TypeError, ValueError):
        return None


def availability_journeys(data):
    """Yield journey objects from Akasa's current availability response."""
    if not isinstance(data, dict):
        return
    for result in data.get("results") or []:
        for trip in result.get("trips") or []:
            for market in trip.get("journeysAvailableByMarket") or []:
                for journey in market.get("value") or []:
                    if isinstance(journey, dict):
                        yield journey


def fare_lookup(data):
    """Index the expanded fare objects by fareAvailabilityKey."""
    lookup = {}
    if not isinstance(data, dict):
        return lookup
    for item in data.get("faresAvailable") or []:
        if not isinstance(item, dict):
            continue
        value = item.get("value") or {}
        key = item.get("key") or value.get("fareAvailabilityKey")
        if key:
            lookup[key] = value
    return lookup


def fare_components(fare_value):
    """Extract base fare, taxes, mandatory fees, and fare family."""
    base_fare = 0.0
    taxes = 0.0
    mandatory_fees = 0.0
    families = []
    found_charge = False

    for fare in fare_value.get("fares") or []:
        family = fare.get("productClass")
        if family and family not in families:
            families.append(family)
        for passenger_fare in fare.get("passengerFares") or []:
            for charge in passenger_fare.get("serviceCharges") or []:
                amount = charge.get("amount")
                if not isinstance(amount, (int, float)):
                    continue
                found_charge = True
                charge_type = charge.get("type")
                if charge_type == "FarePrice":
                    base_fare += amount
                elif charge_type == "Tax":
                    taxes += amount
                elif charge_type == "TravelFee":
                    mandatory_fees += amount

    totals = fare_value.get("totals") or {}
    total_fare = totals.get("fareTotal")
    return {
        "base_fare": base_fare if found_charge else None,
        "taxes": taxes if found_charge else None,
        "mandatory_fees": mandatory_fees if found_charge else None,
        "total_fare": total_fare if isinstance(total_fare, (int, float)) else None,
        "fare_family": "+".join(families) if families else None,
    }


def normalize_response(raw: dict, origin: str, dest: str, travel_date: str,
                        adv: int, route_id: str = None, total_passengers: int = None):
    """
    Prefer the flight-level availability response. The lowFare response is
    only a calendar and is used as a fallback when no flights are returned.
    """
    records = []
    responses = raw.get("responses", {})
    availability = responses.get("availability", {}).get("data")
    fare_data = responses.get("lowFare", {}).get("data")
    now_iso = datetime.now().astimezone().isoformat()

    fares_by_key = fare_lookup(availability)
    for journey in availability_journeys(availability):
        designator = journey.get("designator") or {}
        segments = journey.get("segments") or []
        flight_numbers = []
        for segment in segments:
            identifier = segment.get("identifier") or {}
            number = identifier.get("identifier")
            carrier = identifier.get("carrierCode") or "QP"
            if number:
                flight_numbers.append(f"{carrier}{number}")

        fare_options = []
        for journey_fare in journey.get("fares") or []:
            key = journey_fare.get("fareAvailabilityKey")
            fare_value = fares_by_key.get(key)
            if not fare_value:
                continue
            components = fare_components(fare_value)
            available_counts = [
                detail.get("availableCount")
                for detail in journey_fare.get("details") or []
                if isinstance(detail.get("availableCount"), (int, float))
            ]
            components["seats_available"] = min(available_counts) if available_counts else None
            fare_options.append(components)

        priced_options = [f for f in fare_options if f.get("total_fare") is not None]
        chosen_fare = min(priced_options, key=lambda f: f["total_fare"]) if priced_options else {}
        departure = designator.get("departure")
        arrival = designator.get("arrival")
        records.append({
            "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
            "collection_timestamp": now_iso, "route_id": route_id,
            "total_passengers": total_passengers, "origin": origin,
            "destination": dest, "travel_date": str(departure or travel_date)[:10],
            "advance_purchase_days": adv, "trip_type": "one_way",
            "passenger_count": 1, "cabin": "economy",
            "stops": journey.get("stops"),
            "airline_code": "QP", "airline_name": "Akasa Air",
            "flight_number": "/".join(flight_numbers) if flight_numbers else None,
            "departure_time": departure,
            "arrival_time": arrival,
            "duration_minutes": elapsed_minutes(departure, arrival),
            "fare_family": chosen_fare.get("fare_family"),
            "base_fare": chosen_fare.get("base_fare"),
            "taxes": chosen_fare.get("taxes"),
            "mandatory_fees": chosen_fare.get("mandatory_fees"),
            "total_fare": chosen_fare.get("total_fare"),
            "currency": availability.get("currencyCode", "INR") if isinstance(availability, dict) else "INR",
            "availability_status": "available",
            "seats_available": chosen_fare.get("seats_available"),
            "source": "Akasa Air", "source_type": "airline", "data_quality_score": 100,
            "no_flights": False, "sold_out": False,
        })

    data = fare_data
    if not isinstance(data, dict):
        data = {}
    low_fares = data.get("lowFares") or []
    if not isinstance(low_fares, list):
        low_fares = []

    for fare in low_fares if not records else []:
        fare_date = (fare.get("date") or "")[:10]
        if not fare_date or fare_date != travel_date:
            continue

        price = fare.get("price")
        taxes = fare.get("taxesAndFees")
        available = fare.get("available")
        sold_out = fare.get("soldOut", False)
        no_flights = fare.get("noFlights", False)

        if no_flights:
            availability_status = "no_flights"
        elif sold_out or available == 0:
            availability_status = "sold_out"
        else:
            availability_status = "available"

        # advance_purchase_days is now computed per-row, since each row is
        # a different date in the returned calendar -- not just the one
        # date originally requested.
        try:
            days_out = (datetime.strptime(fare_date, "%Y-%m-%d") - datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0)).days
        except Exception:
            days_out = adv

        records.append({
            "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
            "collection_timestamp": now_iso,
            "route_id": route_id,
            "total_passengers": total_passengers,
            "origin": origin,
            "destination": dest,
            "travel_date": fare_date,
            "advance_purchase_days": days_out,
            "trip_type": "one_way",
            "passenger_count": 1,
            "cabin": "economy",
            "stops": None,
            "airline_code": "QP",
            "airline_name": "Akasa Air",
            "flight_number": None,
            "departure_time": None,
            "arrival_time": None,
            "duration_minutes": None,
            "fare_family": None,
            "base_fare": None,
            "taxes": taxes,
            "mandatory_fees": None,
            "total_fare": price,
            "currency": "INR",
            "availability_status": availability_status,
            "seats_available": available,
            "source": "Akasa Air",
            "source_type": "airline",
            "data_quality_score": 90 if price is not None else 40,
            "no_flights": no_flights,
            "sold_out": sold_out,
        })

    if not records:
        records.append({
            "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
            "collection_timestamp": now_iso,
            "route_id": route_id,
            "total_passengers": total_passengers,
            "origin": origin,
            "destination": dest,
            "travel_date": travel_date,
            "advance_purchase_days": adv,
            "trip_type": "one_way",
            "passenger_count": 1,
            "cabin": "economy",
            "stops": None,
            "airline_code": "QP",
            "airline_name": "Akasa Air",
            "flight_number": None,
            "departure_time": None,
            "arrival_time": None,
            "duration_minutes": None,
            "fare_family": None,
            "base_fare": None,
            "taxes": None,
            "mandatory_fees": None,
            "total_fare": None,
            "currency": "INR",
            "availability_status": "no_flights" if availability is not None else "not_collected",
            "seats_available": 0 if availability is not None else None,
            "source": "Akasa Air",
            "source_type": "airline",
            "data_quality_score": 0,
            "no_flights": True if availability is not None else None,
            "sold_out": False if availability is not None else None,
        })

    return records


# ---------------------------
# BATCH RUNNER (24 routes x five requested advance windows)
# ---------------------------
async def run_batch_scrape(headless: bool = True):
    today = datetime.now()
    normalized_all = []

    total = len(ROUTES_WITH_SLUGS) * len(ADVANCE_WINDOWS)
    print(f"Planned requests: {total} ({len(ROUTES_WITH_SLUGS)} routes x {len(ADVANCE_WINDOWS)} date window)")

    count = 0
    for origin, dest, o_slug, d_slug, route_id, pax in ROUTES_WITH_SLUGS:
        windows = [
            (adv, (today + timedelta(days=adv)).strftime("%Y-%m-%d"))
            for adv in ADVANCE_WINDOWS
        ]
        first_adv, first_date = windows[0]
        print(f"[{count + 1}-{count + len(windows)}/{total}] {route_id} | five windows ...")
        result = await scrape_route(
            origin,
            dest,
            first_date,
            o_slug,
            d_slug,
            headless=headless,
            additional_dates=[date for _, date in windows[1:]],
        )
        window_responses = (result or {}).get("window_responses", {})

        for adv, travel_date in windows:
            count += 1
            window_raw = window_responses.get(travel_date, {})
            normalized_all.extend(
                normalize_response(window_raw, origin, dest, travel_date, adv, route_id, pax)
            )
            status = "OK" if window_raw else "--"
            print(f"  [{status}] T+{adv} | {travel_date}")

        await asyncio.sleep(3)

    out_path = write_output(
        airline_slug="akasaair",
        output_dir=OUTPUT_DIR,
        records=normalized_all,
        meta={"airline": "Akasa Air", "advance_windows": ADVANCE_WINDOWS},
    )

    print(f"\nDone. Processed {total} route windows.")
    print(f"Normalized records: {len(normalized_all)}")
    print(f"Updated: {out_path}")
    return normalized_all


# ---------------------------
# SINGLE-ROUTE TEST
# ---------------------------
async def test_single():
    result = await scrape_route("BOM", "DEL", "2026-08-28", "mumbai", "new-delhi", headless=False)
    if result:
        print("Captured URLs:", {
            name: response.get("url")
            for name, response in result.get("responses", {}).items()
        })
        recs = normalize_response(result, "BOM", "DEL", "2026-08-28", 3, "MUMBAI-DELHI", 4029444)
        print(f"\n{len(recs)} date(s) normalized:\n")
        for r in recs:
            print(f"  {r.get('travel_date')}  |  total_fare: {r.get('total_fare')}  |  "
                  f"taxes: {r.get('taxes')}  |  seats: {r.get('seats_available')}  |  "
                  f"status: {r.get('availability_status')}")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        raw_path = OUTPUT_DIR / f"akasa_raw_test_{stamp}.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump({
                "route_id": "MUMBAI-DELHI",
                "origin": "BOM",
                "destination": "DEL",
                "travel_date": "2026-08-28",
                "scraped_at": datetime.now().isoformat(),
                "source_url": {
                    name: response.get("url")
                    for name, response in result.get("responses", {}).items()
                },
                "raw_response": {
                    name: response.get("data")
                    for name, response in result.get("responses", {}).items()
                },
            }, f, indent=2, ensure_ascii=False)

        norm_path = OUTPUT_DIR / f"akasa_normalized_test_{stamp}.json"
        with open(norm_path, "w", encoding="utf-8") as f:
            json.dump(recs, f, indent=2, ensure_ascii=False)

        print(f"\nRaw saved to:        {raw_path}")
        print(f"Normalized saved to: {norm_path}")
    else:
        print("No data captured. Check data/last_run_debug.png to see what the browser saw.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_single())
    else:
        asyncio.run(run_batch_scrape(headless=True))