# # # # # # # import asyncio
# # # # # # # import json
# # # # # # # import re
# # # # # # # import uuid
# # # # # # # from datetime import datetime, timedelta, timezone
# # # # # # # from pathlib import Path
# # # # # # # from urllib.parse import urlparse
# # # # # # # from urllib.error import HTTPError
# # # # # # # from urllib.request import Request, urlopen
# # # # # # # from urllib.robotparser import RobotFileParser

# # # # # # # from playwright.async_api import async_playwright


# # # # # # # ADVANCE_WINDOWS = [1, 7, 15, 30, 45]
# # # # # # # USER_AGENT = "VAYUSETU-Bot"
# # # # # # # BASE_URL = "https://flights.airindiaexpress.com"
# # # # # # # ROBOTS_URL = f"{BASE_URL}/robots.txt"
# # # # # # # SITEMAP_URL = f"{BASE_URL}/sitemap_index.xml"
# # # # # # # OUTPUT_PATH = Path(__file__).with_name("airindiaexpress_top_24_routes.json")

# # # # # # # CITY_TO_IATA = {
# # # # # # #     "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "HYDERABAD": "HYD",
# # # # # # #     "KOLKATA": "CCU", "PUNE": "PNQ", "GOA": "GOX", "AHMEDABAD": "AMD",
# # # # # # #     "CHENNAI": "MAA", "SRINAGAR": "SXR", "GUWAHATI": "GAU", "PATNA": "PAT",
# # # # # # #     "LUCKNOW": "LKO", "KOCHI": "COK",
# # # # # # # }

# # # # # # # CITY_TO_SLUG = {
# # # # # # #     "DELHI": "delhi", "MUMBAI": "mumbai", "BENGALURU": "bengaluru",
# # # # # # #     "HYDERABAD": "hyderabad", "KOLKATA": "kolkata", "PUNE": "pune", "GOA": "goa",
# # # # # # #     "AHMEDABAD": "ahmedabad", "CHENNAI": "chennai", "SRINAGAR": "srinagar",
# # # # # # #     "GUWAHATI": "guwahati", "PATNA": "patna", "LUCKNOW": "lucknow", "KOCHI": "kochi",
# # # # # # # }

# # # # # # # PRIORITY_ROUTES = [
# # # # # # #     ("DELHI", "MUMBAI", 4029444), ("BENGALURU", "DELHI", 2885936),
# # # # # # #     ("BENGALURU", "MUMBAI", 2476421), ("DELHI", "HYDERABAD", 1862287),
# # # # # # #     ("DELHI", "KOLKATA", 1778985), ("DELHI", "PUNE", 1704284),
# # # # # # #     ("GOA", "MUMBAI", 1495328), ("AHMEDABAD", "DELHI", 1402813),
# # # # # # #     ("DELHI", "GOA", 1352032), ("CHENNAI", "MUMBAI", 1312448),
# # # # # # #     ("HYDERABAD", "MUMBAI", 1285881), ("KOLKATA", "MUMBAI", 1281897),
# # # # # # #     ("CHENNAI", "DELHI", 1277274), ("BENGALURU", "HYDERABAD", 1217734),
# # # # # # #     ("AHMEDABAD", "MUMBAI", 1215086), ("BENGALURU", "KOLKATA", 1204113),
# # # # # # #     ("DELHI", "SRINAGAR", 1141145), ("BENGALURU", "PUNE", 1079353),
# # # # # # #     ("DELHI", "GUWAHATI", 938099), ("DELHI", "PATNA", 908354),
# # # # # # #     ("BENGALURU", "GOA", 875214), ("BENGALURU", "CHENNAI", 872523),
# # # # # # #     ("DELHI", "LUCKNOW", 854555), ("KOCHI", "MUMBAI", 805813),
# # # # # # # ]


# # # # # # # def robots_allowed(url):
# # # # # # #     parser = RobotFileParser()
# # # # # # #     parser.set_url(ROBOTS_URL)
# # # # # # #     try:
# # # # # # #         request = Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
# # # # # # #         with urlopen(request, timeout=30) as response:
# # # # # # #             parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
# # # # # # #     except HTTPError as exc:
# # # # # # #         # RFC 9309 section 2.3.1.4: 400-499 means robots.txt is
# # # # # # #         # unavailable and the crawler may access resources.
# # # # # # #         if 400 <= exc.code <= 499 and exc.code != 429:
# # # # # # #             return True
# # # # # # #         print(f"[!] Could not read {ROBOTS_URL}: HTTP {exc.code}")
# # # # # # #         return False
# # # # # # #     except Exception as exc:
# # # # # # #         print(f"[!] Could not read {ROBOTS_URL}: {exc}")
# # # # # # #         return False
# # # # # # #     return parser.can_fetch(USER_AGENT, url)


# # # # # # # def route_url(origin_city, destination_city):
# # # # # # #     origin = CITY_TO_SLUG[origin_city]
# # # # # # #     destination = CITY_TO_SLUG[destination_city]
# # # # # # #     return f"{BASE_URL}/en-in/{origin}-to-{destination}-flights"


# # # # # # # def parse_fares(text, origin, destination):
# # # # # # #     pattern = re.compile(
# # # # # # #         rf"{origin}[–-]{destination},\s+([A-Za-z]{{3}},\s+[A-Za-z]{{3}}\s+\d{{1,2}}\s+\d{{4}}):\s+From\s+₹([\d,]+)",
# # # # # # #         re.IGNORECASE,
# # # # # # #     )
# # # # # # #     fares = {}
# # # # # # #     for date_text, amount in pattern.findall(text):
# # # # # # #         try:
# # # # # # #             date = datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")
# # # # # # #             fares[date] = float(amount.replace(",", ""))
# # # # # # #         except ValueError:
# # # # # # #             continue
# # # # # # #     return fares


# # # # # # # def parse_duration(value):
# # # # # # #     match = re.search(r"(?:(\d+)h)?\s*(?:(\d+)m)?", value or "")
# # # # # # #     if not match or not any(match.groups()):
# # # # # # #         return None
# # # # # # #     return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


# # # # # # # def parse_schedules(text, origin, destination):
# # # # # # #     heading = re.search(r"Flight Schedule", text, re.IGNORECASE)
# # # # # # #     if not heading:
# # # # # # #         return []
# # # # # # #     section = text[heading.end():]
# # # # # # #     disclaimer = re.search(r"Disclaimer:\s*Flight timings", section, re.IGNORECASE)
# # # # # # #     if disclaimer:
# # # # # # #         section = section[:disclaimer.start()]
# # # # # # #     lines = [line.strip() for line in section.splitlines() if line.strip()]
# # # # # # #     starts = [index for index, line in enumerate(lines) if re.fullmatch(r"(?:IX|I5)\s*\d+", line)]
# # # # # # #     schedules = []
# # # # # # #     for position, start in enumerate(starts):
# # # # # # #         block = lines[start:(starts[position + 1] if position + 1 < len(starts) else len(lines))]
# # # # # # #         try:
# # # # # # #             origin_at = block.index(origin)
# # # # # # #             destination_at = block.index(destination, origin_at + 1)
# # # # # # #         except ValueError:
# # # # # # #             continue
# # # # # # #         times = [line for line in block[destination_at + 1:] if re.fullmatch(r"\d{1,2}:\d{2}(?:\s*\(\+1\))?", line)]
# # # # # # #         duration = next((parse_duration(line) for line in block if re.fullmatch(r"(?:\d+h\s*)?(?:\d+m)", line)), None)
# # # # # # #         if len(times) < 2:
# # # # # # #             continue
# # # # # # #         stop_label = block[origin_at + 1] if origin_at + 1 < destination_at else ""
# # # # # # #         schedules.append({
# # # # # # #             "flight_number": block[0].replace(" ", ""),
# # # # # # #             "stops": 0 if "non-stop" in stop_label.lower() else None,
# # # # # # #             "departure_clock": times[0].split()[0],
# # # # # # #             "arrival_clock": times[1].split()[0],
# # # # # # #             "arrival_next_day": "+1" in times[1],
# # # # # # #             "duration_minutes": duration,
# # # # # # #         })
# # # # # # #     return schedules


# # # # # # # async def collect_route(page, origin_city, destination_city, target_dates):
# # # # # # #     origin = CITY_TO_IATA[origin_city]
# # # # # # #     destination = CITY_TO_IATA[destination_city]
# # # # # # #     url = route_url(origin_city, destination_city)
# # # # # # #     if not robots_allowed(url):
# # # # # # #         print(f"[!] Robots policy disallows {url}")
# # # # # # #         return {}, [], url, "robots_disallowed"
# # # # # # #     # AirTRFX keeps background requests open, so "networkidle" can time out even
# # # # # # #     # after the published fare page is usable.  DOM readiness is sufficient for
# # # # # # #     # reading the server-rendered fare calendar and schedule text.
# # # # # # #     response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
# # # # # # #     if not response or response.status != 200:
# # # # # # #         return {}, [], url, f"http_{response.status if response else 'none'}"

# # # # # # #     fares = {}
# # # # # # #     body = await page.locator("body").inner_text()
# # # # # # #     fares.update(parse_fares(body, origin, destination))
# # # # # # #     schedules = parse_schedules(body, origin, destination)

# # # # # # #     missing_months = sorted({
# # # # # # #         datetime.strptime(date, "%Y-%m-%d").strftime("%b %Y")
# # # # # # #         for date in target_dates if date not in fares
# # # # # # #     })
# # # # # # #     for month_label in missing_months:
# # # # # # #         try:
# # # # # # #             carousel = page.locator("section[aria-label='Month selection carousel']")
# # # # # # #             month = carousel.get_by_text(month_label, exact=True)
# # # # # # #             if await month.count() == 0:
# # # # # # #                 continue
# # # # # # #             await month.first.click(timeout=3000)
# # # # # # #             await page.wait_for_timeout(1000)
# # # # # # #             body = await page.locator("body").inner_text()
# # # # # # #             fares.update(parse_fares(body, origin, destination))
# # # # # # #         except Exception:
# # # # # # #             break
# # # # # # #     return fares, schedules, url, None


# # # # # # # def normalized_record(route_id, passengers, origin, destination, travel_date, advance_days,
# # # # # # #                       source_url, fare=None, schedule=None, error=None):
# # # # # # #     schedule = schedule or {}
# # # # # # #     departure_time = None
# # # # # # #     arrival_time = None
# # # # # # #     if schedule.get("departure_clock"):
# # # # # # #         departure_time = f"{travel_date}T{schedule['departure_clock']}:00"
# # # # # # #     if schedule.get("arrival_clock"):
# # # # # # #         arrival_date = datetime.strptime(travel_date, "%Y-%m-%d")
# # # # # # #         if schedule.get("arrival_next_day") or schedule["arrival_clock"] <= schedule.get("departure_clock", ""):
# # # # # # #             arrival_date += timedelta(days=1)
# # # # # # #         arrival_time = f"{arrival_date:%Y-%m-%d}T{schedule['arrival_clock']}:00"
# # # # # # #     available = fare is not None
# # # # # # #     return {
# # # # # # #         "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
# # # # # # #         "collection_timestamp": datetime.now().astimezone().isoformat(),
# # # # # # #         "route_id": route_id,
# # # # # # #         "total_passengers": passengers,
# # # # # # #         "origin": origin,
# # # # # # #         "destination": destination,
# # # # # # #         "travel_date": travel_date,
# # # # # # #         "advance_purchase_days": advance_days,
# # # # # # #         "trip_type": "one_way",
# # # # # # #         "passenger_count": 1,
# # # # # # #         "cabin": "economy",
# # # # # # #         "stops": schedule.get("stops"),
# # # # # # #         "airline_code": "IX",
# # # # # # #         "airline_name": "Air India Express",
# # # # # # #         "flight_number": schedule.get("flight_number"),
# # # # # # #         "departure_time": departure_time,
# # # # # # #         "arrival_time": arrival_time,
# # # # # # #         "duration_minutes": schedule.get("duration_minutes"),
# # # # # # #         "fare_family": "Economy" if available else None,
# # # # # # #         "base_fare": None,
# # # # # # #         "taxes": None,
# # # # # # #         "mandatory_fees": None,
# # # # # # #         "total_fare": fare,
# # # # # # #         "currency": "INR",
# # # # # # #         "availability_status": "available" if available else ("collection_error" if error else "not_published"),
# # # # # # #         "seats_available": None,
# # # # # # #         "source": "Air India Express",
# # # # # # #         "source_type": "airline_published_fare_page",
# # # # # # #         "data_quality_score": 75 if available and schedule else (60 if available else 0),
# # # # # # #         "no_flights": False if available else None,
# # # # # # #         "sold_out": None,
# # # # # # #         "source_url": source_url,
# # # # # # #         "note": error,
# # # # # # #     }


# # # # # # # async def run_batch_scrape(headless=True):
# # # # # # #     today = datetime.now()
# # # # # # #     windows = [(days, (today + timedelta(days=days)).strftime("%Y-%m-%d")) for days in ADVANCE_WINDOWS]
# # # # # # #     records = []
# # # # # # #     async with async_playwright() as playwright:
# # # # # # #         browser = await playwright.chromium.launch(headless=headless)
# # # # # # #         page = await browser.new_page(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})
# # # # # # #         for index, (origin_city, destination_city, passengers) in enumerate(PRIORITY_ROUTES, 1):
# # # # # # #             origin = CITY_TO_IATA[origin_city]
# # # # # # #             destination = CITY_TO_IATA[destination_city]
# # # # # # #             route_id = f"{origin_city}-{destination_city}"
# # # # # # #             print(f"[{index}/{len(PRIORITY_ROUTES)}] {route_id}")
# # # # # # #             target_dates = [date for _, date in windows]
# # # # # # #             try:
# # # # # # #                 fares, schedules, source_url, error = await collect_route(
# # # # # # #                     page, origin_city, destination_city, target_dates
# # # # # # #                 )
# # # # # # #             except Exception as exc:
# # # # # # #                 fares, schedules, source_url, error = {}, [], route_url(origin_city, destination_city), str(exc)
# # # # # # #             for advance_days, travel_date in windows:
# # # # # # #                 fare = fares.get(travel_date)
# # # # # # #                 if schedules and fare is not None:
# # # # # # #                     for schedule in schedules:
# # # # # # #                         records.append(normalized_record(
# # # # # # #                             route_id, passengers, origin, destination, travel_date, advance_days,
# # # # # # #                             source_url, fare, schedule, error,
# # # # # # #                         ))
# # # # # # #                 else:
# # # # # # #                     records.append(normalized_record(
# # # # # # #                         route_id, passengers, origin, destination, travel_date, advance_days,
# # # # # # #                         source_url, fare, None, error,
# # # # # # #                     ))
# # # # # # #             await asyncio.sleep(3)
# # # # # # #         await browser.close()

# # # # # # #     output = {
# # # # # # #         "airline": "Air India Express",
# # # # # # #         "base_url": BASE_URL,
# # # # # # #         "robots_url": ROBOTS_URL,
# # # # # # #         "robots_available": True,
# # # # # # #         "crawl_allowed": True,
# # # # # # #         "user_agent": USER_AGENT,
# # # # # # #         "crawl_delay": None,
# # # # # # #         "disallowed_paths": [],
# # # # # # #         "sitemaps": [SITEMAP_URL],
# # # # # # #         "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
# # # # # # #         "advance_windows": ADVANCE_WINDOWS,
# # # # # # #         "routes": records,
# # # # # # #     }
# # # # # # #     with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
# # # # # # #         json.dump(output, file, indent=2, ensure_ascii=False)
# # # # # # #     print(f"Wrote {len(records)} records to {OUTPUT_PATH}")
# # # # # # #     return records


# # # # # # # if __name__ == "__main__":
# # # # # # #     asyncio.run(run_batch_scrape())
# # # # # # import asyncio
# # # # # # import json
# # # # # # from datetime import datetime, timedelta
# # # # # # from pathlib import Path

# # # # # # import httpx
# # # # # # from playwright.async_api import async_playwright


# # # # # # # ---------- CONFIG ----------
# # # # # # OUTPUT_DIR = Path(__file__).with_name("airindiaexpress")
# # # # # # OUTPUT_DIR.mkdir(exist_ok=True)

# # # # # # BASE_API = "https://api.airindiaexpress.com/b2c-flightsearch/v2/lowFares"
# # # # # # FSA_URL_TEMPLATE = (
# # # # # #     "https://www.airindiaexpress.com/flight-availability?"
# # # # # #     "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
# # # # # # )

# # # # # # HEADERS = {
# # # # # #     "User-Agent": (
# # # # # #         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
# # # # # #         "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# # # # # #     ),
# # # # # #     "Content-Type": "application/json",
# # # # # #     "Accept": "application/json, text/plain, */*",
# # # # # #     "Referer": "https://www.airindiaexpress.com/",
# # # # # #     "Origin": "https://www.airindiaexpress.com",
# # # # # # }


# # # # # # def timestamp():
# # # # # #     return datetime.now().strftime("%Y%m%d_%H%M%S")


# # # # # # def output_json_path(origin, destination):
# # # # # #     return OUTPUT_DIR / f"{origin}_{destination}_lowfares_{timestamp()}.json"


# # # # # # def output_screenshot_path(origin, destination, label="page"):
# # # # # #     return OUTPUT_DIR / f"{origin}_{destination}_{label}_{timestamp()}.png"


# # # # # # # ---------- API-BASED FARE FETCH ----------
# # # # # # async def fetch_low_fares_api(client: httpx.AsyncClient, origin, destination, start_date, end_date):
# # # # # #     payload = {
# # # # # #         "origin": origin,
# # # # # #         "destination": destination,
# # # # # #         "startDate": start_date,   # "YYYY-MM-DD"
# # # # # #         "endDate": end_date,       # "YYYY-MM-DD"
# # # # # #         "currencyCode": "INR",
# # # # # #         "fareType": "None",
# # # # # #         "includeTaxesAndFees": True,
# # # # # #         "numberOfPassengers": 1,
# # # # # #     }
# # # # # #     try:
# # # # # #         resp = await client.post(BASE_API, json=payload, headers=HEADERS, timeout=30)
# # # # # #         resp.raise_for_status()
# # # # # #         data = resp.json()
# # # # # #         return data.get("lowFares", []), None
# # # # # #     except Exception as exc:
# # # # # #         return [], str(exc)


# # # # # # # ---------- PLAYWRIGHT SCREENSHOT ----------
# # # # # # async def capture_screenshot(page, origin, destination, label="page"):
# # # # # #     path = output_screenshot_path(origin, destination, label)
# # # # # #     try:
# # # # # #         await page.screenshot(path=str(path), full_page=True)
# # # # # #         print(f"[screenshot] saved -> {path}")
# # # # # #     except Exception as exc:
# # # # # #         print(f"[!] screenshot failed for {origin}-{destination}: {exc}")


# # # # # # async def visit_and_screenshot(playwright, origin, destination, date_str, headless=True):
# # # # # #     browser = await playwright.chromium.launch(headless=headless)
# # # # # #     page = await browser.new_page(
# # # # # #         user_agent=HEADERS["User-Agent"], viewport={"width": 1366, "height": 768}
# # # # # #     )
# # # # # #     url = FSA_URL_TEMPLATE.format(origin=origin, destination=destination, date=date_str)
# # # # # #     try:
# # # # # #         await page.goto(url, wait_until="domcontentloaded", timeout=60000)
# # # # # #         await page.wait_for_timeout(3000)
# # # # # #         await capture_screenshot(page, origin, destination, label="flight_availability")
# # # # # #     except Exception as exc:
# # # # # #         print(f"[!] page visit failed for {origin}-{destination}: {exc}")
# # # # # #     finally:
# # # # # #         await browser.close()


# # # # # # # ---------- MAIN RUN ----------
# # # # # # async def run_for_route(origin, destination, start_date: datetime, days_ahead=30, take_screenshot=True):
# # # # # #     end_date = start_date + timedelta(days=days_ahead)
# # # # # #     start_str = start_date.strftime("%Y-%m-%d")
# # # # # #     end_str = end_date.strftime("%Y-%m-%d")

# # # # # #     async with httpx.AsyncClient() as client:
# # # # # #         fares, error = await fetch_low_fares_api(client, origin, destination, start_str, end_str)

# # # # # #     if error:
# # # # # #         print(f"[!] {origin}-{destination}: {error}")
# # # # # #     else:
# # # # # #         print(f"[{origin}-{destination}] {start_str} to {end_str}: {len(fares)} fare rows")

# # # # # #     output = {
# # # # # #         "airline": "Air India Express",
# # # # # #         "origin": origin,
# # # # # #         "destination": destination,
# # # # # #         "run_timestamp": datetime.now().isoformat(),
# # # # # #         "start_date": start_str,
# # # # # #         "end_date": end_str,
# # # # # #         "lowFares": fares,
# # # # # #         "error": error,
# # # # # #     }

# # # # # #     out_path = output_json_path(origin, destination)
# # # # # #     with open(out_path, "w", encoding="utf-8") as f:
# # # # # #         json.dump(output, f, indent=2, ensure_ascii=False)
# # # # # #     print(f"[json] saved -> {out_path}")

# # # # # #     if take_screenshot:
# # # # # #         async with async_playwright() as playwright:
# # # # # #             await visit_and_screenshot(playwright, origin, destination, start_str)

# # # # # #     return out_path


# # # # # # async def main():
# # # # # #     origin, destination = "DEL", "BOM"
# # # # # #     start_date = datetime.now()
# # # # # #     await run_for_route(origin, destination, start_date, days_ahead=30, take_screenshot=True)


# # # # # # if __name__ == "__main__":
# # # # # #     asyncio.run(main())
# # # # # import asyncio
# # # # # import json
# # # # # from datetime import datetime, timedelta
# # # # # from pathlib import Path

# # # # # from playwright.async_api import async_playwright


# # # # # OUTPUT_DIR = Path(__file__).with_name("airindiaexpress")
# # # # # OUTPUT_DIR.mkdir(exist_ok=True)

# # # # # FSA_URL_TEMPLATE = (
# # # # #     "https://www.airindiaexpress.com/flight-availability?"
# # # # #     "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
# # # # # )

# # # # # USER_AGENT = (
# # # # #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
# # # # #     "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# # # # # )


# # # # # def timestamp():
# # # # #     return datetime.now().strftime("%Y%m%d_%H%M%S")


# # # # # def output_json_path(origin, destination):
# # # # #     return OUTPUT_DIR / f"{origin}_{destination}_lowfares_{timestamp()}.json"


# # # # # def output_screenshot_path(origin, destination, label="page"):
# # # # #     return OUTPUT_DIR / f"{origin}_{destination}_{label}_{timestamp()}.png"


# # # # # async def fetch_low_fares_via_browser(origin, destination, start_date, headless=True):
# # # # #     captured = {}

# # # # #     async def handle_response(response):
# # # # #         if "b2c-flightsearch/v2/lowFares" in response.url and response.request.method == "POST":
# # # # #             try:
# # # # #                 data = await response.json()
# # # # #                 captured["data"] = data
# # # # #             except Exception as exc:
# # # # #                 captured["error"] = str(exc)

# # # # #     async with async_playwright() as playwright:
# # # # #         browser = await playwright.chromium.launch(headless=headless)
# # # # #         page = await browser.new_page(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})
# # # # #         page.on("response", handle_response)

# # # # #         url = FSA_URL_TEMPLATE.format(origin=origin, destination=destination, date=start_date)
# # # # #         try:
# # # # #             await page.goto(url, wait_until="domcontentloaded", timeout=60000)
# # # # #             # wait for the lowFares XHR to fire and resolve
# # # # #             await page.wait_for_timeout(6000)

# # # # #             screenshot_path = output_screenshot_path(origin, destination, "flight_availability")
# # # # #             await page.screenshot(path=str(screenshot_path), full_page=True)
# # # # #             print(f"[screenshot] saved -> {screenshot_path}")
# # # # #         except Exception as exc:
# # # # #             print(f"[!] page load failed: {exc}")
# # # # #         finally:
# # # # #             await browser.close()

# # # # #     return captured


# # # # # async def run_for_route(origin, destination, start_date: datetime, headless=True):
# # # # #     start_str = start_date.strftime("%Y-%m-%d")
# # # # #     result = await fetch_low_fares_via_browser(origin, destination, start_str, headless=headless)

# # # # #     fares = result.get("data", {}).get("lowFares", [])
# # # # #     error = result.get("error")

# # # # #     if error:
# # # # #         print(f"[!] {origin}-{destination}: {error}")
# # # # #     elif not fares:
# # # # #         print(f"[!] {origin}-{destination}: no lowFares captured (network response may not have fired in time)")
# # # # #     else:
# # # # #         print(f"[{origin}-{destination}] {len(fares)} fare rows captured")

# # # # #     output = {
# # # # #         "airline": "Air India Express",
# # # # #         "origin": origin,
# # # # #         "destination": destination,
# # # # #         "run_timestamp": datetime.now().isoformat(),
# # # # #         "start_date": start_str,
# # # # #         "lowFares": fares,
# # # # #         "error": error,
# # # # #     }

# # # # #     out_path = output_json_path(origin, destination)
# # # # #     with open(out_path, "w", encoding="utf-8") as f:
# # # # #         json.dump(output, f, indent=2, ensure_ascii=False)
# # # # #     print(f"[json] saved -> {out_path}")

# # # # #     return out_path


# # # # # async def main():
# # # # #     origin, destination = "DEL", "BOM"
# # # # #     await run_for_route(origin, destination, datetime.now(), headless=True)


# # # # # if __name__ == "__main__":
# # # # #     asyncio.run(main())
# # # # import asyncio
# # # # import json
# # # # from datetime import datetime
# # # # from pathlib import Path
# # # # from playwright.async_api import async_playwright

# # # # OUTPUT_DIR = Path(__file__).with_name("airindiaexpress")
# # # # OUTPUT_DIR.mkdir(exist_ok=True)

# # # # FSA_URL_TEMPLATE = (
# # # #     "https://www.airindiaexpress.com/flight-availability?"
# # # #     "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
# # # # )

# # # # def timestamp():
# # # #     return datetime.now().strftime("%Y%m%d_%H%M%S")

# # # # def output_json_path(origin, destination):
# # # #     return OUTPUT_DIR / f"{origin}_{destination}_fares_{timestamp()}.json"

# # # # def output_screenshot_path(origin, destination):
# # # #     return OUTPUT_DIR / f"{origin}_{destination}_flight_availability_{timestamp()}.png"


# # # # async def fetch_fares_via_browser(origin, destination, start_date, headless=True):
# # # #     result = {"data": [], "error": None, "raw_responses": []}

# # # #     async with async_playwright() as playwright:
# # # #         # --headless=new avoids the "HeadlessChrome" UA string that Akamai flags
# # # #         browser = await playwright.chromium.launch(
# # # #             headless=headless,
# # # #             args=["--headless=new"] if headless else [],
# # # #         )
# # # #         context = await browser.new_context(
# # # #             viewport={"width": 1366, "height": 768},
# # # #             locale="en-IN",
# # # #         )
# # # #         page = await context.new_page()

# # # #         async def handle_response(response):
# # # #             if "search-availability-for-discount" in response.url and response.request.method == "POST":
# # # #                 try:
# # # #                     data = await response.json()
# # # #                     result["raw_responses"].append(data)
# # # #                 except Exception as exc:
# # # #                     result["error"] = f"parse error: {exc}"

# # # #         page.on("response", handle_response)

# # # #         url = FSA_URL_TEMPLATE.format(origin=origin, destination=destination, date=start_date)
# # # #         try:
# # # #             await page.goto(url, wait_until="domcontentloaded", timeout=60000)
# # # #             # give it enough time for auth token + recaptcha + the actual fare call to complete
# # # #             await page.wait_for_timeout(15000)
# # # #         except Exception as exc:
# # # #             result["error"] = f"navigation error: {exc}"

# # # #         try:
# # # #             screenshot_path = output_screenshot_path(origin, destination)
# # # #             await page.screenshot(path=str(screenshot_path), full_page=True)
# # # #             print(f"[screenshot] saved -> {screenshot_path}")
# # # #         except Exception as exc:
# # # #             print(f"[!] screenshot failed: {exc}")

# # # #         await browser.close()

# # # #     return result


# # # # async def run_for_route(origin, destination, start_date: datetime, headless=True):
# # # #     start_str = start_date.strftime("%Y-%m-%d")
# # # #     result = await fetch_fares_via_browser(origin, destination, start_str, headless=headless)

# # # #     responses = result["raw_responses"]
# # # #     error = result["error"]

# # # #     if error:
# # # #         print(f"[!] {origin}-{destination}: {error}")
# # # #     elif not responses:
# # # #         print(f"[!] {origin}-{destination}: search-availability-for-discount never captured")
# # # #     else:
# # # #         print(f"[{origin}-{destination}] {len(responses)} response(s) captured")

# # # #     output = {
# # # #         "airline": "Air India Express",
# # # #         "origin": origin,
# # # #         "destination": destination,
# # # #         "run_timestamp": datetime.now().isoformat(),
# # # #         "start_date": start_str,
# # # #         "responses": responses,
# # # #         "error": error,
# # # #     }

# # # #     out_path = output_json_path(origin, destination)
# # # #     with open(out_path, "w", encoding="utf-8") as f:
# # # #         json.dump(output, f, indent=2, ensure_ascii=False)
# # # #     print(f"[json] saved -> {out_path}")

# # # #     return out_path


# # # # async def main():
# # # #     origin, destination = "DEL", "BOM"
# # # #     await run_for_route(origin, destination, datetime.now(), headless=True)


# # # # if __name__ == "__main__":
# # # #     asyncio.run(main())
# # # import asyncio
# # # import json
# # # import uuid
# # # from datetime import datetime, timedelta, timezone
# # # from pathlib import Path
# # # from urllib.parse import urlparse
# # # from urllib.robotparser import RobotFileParser

# # # from playwright.async_api import async_playwright

# # # # ---------------------------
# # # # CONFIG
# # # # ---------------------------

# # # ADVANCE_WINDOWS = [1, 7, 15, 30]

# # # DELAY_BETWEEN_ROUTES = 15
# # # CONSECUTIVE_FAILURE_BACKOFF = 60
# # # MAX_CONSECUTIVE_FAILURES = 5
# # # MAX_RETRIES_PER_DATE = 3
# # # RETRY_BACKOFF_BASE = 20

# # # OUTPUT_DIR = Path("airindiaexpress")
# # # OUTPUT_DIR.mkdir(exist_ok=True)
# # # CONFIG_OUTPUT_PATH = OUTPUT_DIR / "airindiaexpress_top_24_routes.json"

# # # USER_AGENT = (
# # #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
# # #     "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# # # )

# # # FSA_URL_TEMPLATE = (
# # #     "https://www.airindiaexpress.com/flight-availability?"
# # #     "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
# # # )

# # # FARE_API_PATH = "search-availability-for-discount"

# # # ROBOTS_CACHE = {}


# # # def robots_allowed(url: str) -> bool:
# # #     parsed = urlparse(url)
# # #     robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
# # #     parser = ROBOTS_CACHE.get(robots_url)
# # #     if parser is None:
# # #         parser = RobotFileParser(robots_url)
# # #         try:
# # #             parser.read()
# # #         except Exception as exc:
# # #             print(f"  [!] Could not read {robots_url}: {exc}; skipping URL")
# # #             return False
# # #         ROBOTS_CACHE[robots_url] = parser
# # #     return parser.can_fetch("*", url)


# # # CITY_TO_IATA = {
# # #     "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "HYDERABAD": "HYD",
# # #     "KOLKATA": "CCU", "PUNE": "PNQ", "GOA": "GOX", "AHMEDABAD": "AMD",
# # #     "CHENNAI": "MAA", "SRINAGAR": "SXR", "GUWAHATI": "GAU", "PATNA": "PAT",
# # #     "LUCKNOW": "LKO", "KOCHI": "COK",
# # # }

# # # PRIORITY_ROUTES = [
# # #     ("DELHI", "MUMBAI", 4029444), ("BENGALURU", "DELHI", 2885936),
# # #     ("BENGALURU", "MUMBAI", 2476421), ("DELHI", "HYDERABAD", 1862287),
# # #     ("DELHI", "KOLKATA", 1778985), ("DELHI", "PUNE", 1704284),
# # #     ("GOA", "MUMBAI", 1495328), ("AHMEDABAD", "DELHI", 1402813),
# # #     ("DELHI", "GOA", 1352032), ("CHENNAI", "MUMBAI", 1312448),
# # #     ("HYDERABAD", "MUMBAI", 1285881), ("KOLKATA", "MUMBAI", 1281897),
# # #     ("CHENNAI", "DELHI", 1277274), ("BENGALURU", "HYDERABAD", 1217734),
# # #     ("AHMEDABAD", "MUMBAI", 1215086), ("BENGALURU", "KOLKATA", 1204113),
# # #     ("DELHI", "SRINAGAR", 1141145), ("BENGALURU", "PUNE", 1079353),
# # #     ("DELHI", "GUWAHATI", 938099), ("DELHI", "PATNA", 908354),
# # #     ("BENGALURU", "GOA", 875214), ("BENGALURU", "CHENNAI", 872523),
# # #     ("DELHI", "LUCKNOW", 854555), ("KOCHI", "MUMBAI", 805813),
# # # ]


# # # def build_routes():
# # #     routes = []
# # #     for o_city, d_city, pax in PRIORITY_ROUTES:
# # #         o_code = CITY_TO_IATA.get(o_city, o_city[:3])
# # #         d_code = CITY_TO_IATA.get(d_city, d_city[:3])
# # #         route_id = f"{o_city}-{d_city}"
# # #         routes.append((o_code, d_code, route_id, pax))
# # #     return routes


# # # ROUTES = build_routes()


# # # # ---------------------------
# # # # NULL SANITIZER
# # # # ---------------------------
# # # NUMERIC_FIELDS = {
# # #     "total_passengers", "advance_purchase_days", "passenger_count",
# # #     "stops", "duration_minutes", "base_fare", "taxes",
# # #     "mandatory_fees", "total_fare", "seats_available",
# # #     "data_quality_score", "discount_amount", "discount_percent",
# # #     "initial_price",
# # # }
# # # STRING_FIELDS = {
# # #     "route_id", "origin", "destination", "travel_date", "trip_type",
# # #     "cabin", "airline_code", "airline_name", "flight_number",
# # #     "departure_time", "arrival_time", "fare_family", "currency",
# # #     "availability_status", "source", "source_type", "scrape_outcome",
# # # }
# # # BOOL_FIELDS = {"no_flights", "sold_out"}


# # # def sanitize_record(record: dict) -> dict:
# # #     clean = dict(record)
# # #     for key, value in clean.items():
# # #         if value is not None:
# # #             continue
# # #         if key in NUMERIC_FIELDS:
# # #             clean[key] = 0
# # #         elif key in BOOL_FIELDS:
# # #             clean[key] = False
# # #         elif key in STRING_FIELDS:
# # #             clean[key] = "N/A"
# # #         else:
# # #             clean[key] = "N/A"
# # #     if "scrape_outcome" not in clean:
# # #         clean["scrape_outcome"] = "ok"
# # #     return clean


# # # # ---------------------------
# # # # CORE SCRAPE FUNCTION
# # # # ---------------------------
# # # async def scrape_single_date(origin: str, dest: str, travel_date: str, browser):
# # #     """
# # #     Fresh browser context per date. Intercepts the real fare API
# # #     (search-availability-for-discount) fired by the site's own JS
# # #     when the flight-availability page loads.
# # #     """
# # #     captured = {"responses": []}

# # #     async def handle_response(response, captured=captured):
# # #         if response.status != 200:
# # #             return
# # #         if FARE_API_PATH not in response.url or response.request.method != "POST":
# # #             return
# # #         try:
# # #             body = await response.json()
# # #             captured["responses"].append(body)
# # #         except Exception:
# # #             pass

# # #     search_url = FSA_URL_TEMPLATE.format(origin=origin, destination=dest, date=travel_date)
# # #     if not robots_allowed(search_url):
# # #         print(f"  [!] Robots policy disallows {search_url}")
# # #         return captured, "robots_disallowed"

# # #     context = await browser.new_context(
# # #         user_agent=USER_AGENT,
# # #         viewport={"width": 1366, "height": 768},
# # #         locale="en-IN",
# # #     )
# # #     page = await context.new_page()
# # #     page.on("response", handle_response)

# # #     outcome = "ok"
# # #     try:
# # #         resp = await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
# # #         status = resp.status if resp is not None else None
# # #         print(f"  [i] page load status={status} for {origin}->{dest} {travel_date}")

# # #         deadline = asyncio.get_event_loop().time() + 15
# # #         while asyncio.get_event_loop().time() < deadline:
# # #             if captured["responses"]:
# # #                 break
# # #             await page.wait_for_timeout(1000)

# # #         if not captured["responses"]:
# # #             try:
# # #                 no_flights_visible = await page.locator(
# # #                     "text=/sorry.*no.*flight/i, text=/no flights? found/i"
# # #                 ).first.is_visible(timeout=1000)
# # #             except Exception:
# # #                 no_flights_visible = False

# # #             if no_flights_visible:
# # #                 outcome = "genuine_no_flights"
# # #             else:
# # #                 try:
# # #                     rate_limited = await page.locator(
# # #                         "text=/take a break/i, text=/tried a few times/i"
# # #                     ).first.is_visible(timeout=1000)
# # #                 except Exception:
# # #                     rate_limited = False
# # #                 outcome = "rate_limited" if rate_limited else "no_api_captured"

# # #                 shot_path = OUTPUT_DIR / f"debug_{origin}_{dest}_{travel_date}.png"
# # #                 try:
# # #                     await page.screenshot(path=str(shot_path), full_page=True)
# # #                     print(f"  [!] {outcome} -- screenshot saved: {shot_path}")
# # #                 except Exception:
# # #                     pass
# # #     except Exception as e:
# # #         print(f"  [!] Navigation error for {origin}->{dest} {travel_date}: {e}")
# # #         outcome = "nav_error"
# # #     finally:
# # #         page.remove_listener("response", handle_response)
# # #         await context.close()

# # #     return captured, outcome


# # # async def scrape_date_with_retries(origin: str, dest: str, travel_date: str, browser):
# # #     last_outcome = "not_attempted"
# # #     for attempt in range(1, MAX_RETRIES_PER_DATE + 1):
# # #         captured, outcome = await scrape_single_date(origin, dest, travel_date, browser)
# # #         last_outcome = outcome

# # #         has_valid_fares = any(
# # #             r.get("status", {}).get("message") == "Success" and r.get("onwardJourneyFareList")
# # #             for r in captured["responses"]
# # #         )

# # #         if has_valid_fares or outcome == "genuine_no_flights":
# # #             if attempt > 1:
# # #                 print(f"  [i] Resolved after {attempt} attempt(s): outcome={outcome}")
# # #             return captured, outcome

# # #         if outcome == "rate_limited":
# # #             backoff = RETRY_BACKOFF_BASE * attempt * 2
# # #         else:
# # #             backoff = RETRY_BACKOFF_BASE * attempt

# # #         if attempt < MAX_RETRIES_PER_DATE:
# # #             print(f"  [!] Attempt {attempt}/{MAX_RETRIES_PER_DATE} failed ({outcome}) "
# # #                   f"-- retrying in {backoff}s")
# # #             await asyncio.sleep(backoff)

# # #     print(f"  [!] Exhausted {MAX_RETRIES_PER_DATE} attempts for {origin}->{dest} {travel_date} "
# # #           f"-- recording as blocked (last outcome: {last_outcome})")
# # #     return {"responses": []}, "blocked_after_retries"


# # # async def scrape_route(origin: str, dest: str, travel_dates: list, browser):
# # #     results = {}
# # #     outcomes = {}
# # #     consecutive_failures = 0

# # #     for travel_date in travel_dates:
# # #         if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
# # #             print(f"  [!] {consecutive_failures} consecutive failures -- cooling down {CONSECUTIVE_FAILURE_BACKOFF}s")
# # #             await asyncio.sleep(CONSECUTIVE_FAILURE_BACKOFF)
# # #             consecutive_failures = 0

# # #         captured, outcome = await scrape_date_with_retries(origin, dest, travel_date, browser)
# # #         results[travel_date] = captured
# # #         outcomes[travel_date] = outcome

# # #         has_valid_fares = any(
# # #             r.get("status", {}).get("message") == "Success" and r.get("onwardJourneyFareList")
# # #             for r in captured["responses"]
# # #         )

# # #         if outcome in ("ok", "genuine_no_flights") or has_valid_fares:
# # #             consecutive_failures = 0
# # #         else:
# # #             consecutive_failures += 1

# # #         await asyncio.sleep(RETRY_BACKOFF_BASE / 2)

# # #     return results, outcomes


# # # # ---------------------------
# # # # NORMALIZATION
# # # # ---------------------------
# # # def best_fare_from_responses(responses: list):
# # #     """Pick the lowest finalPriceAfterDiscount across all successful
# # #     fare lists returned in the batch of intercepted responses."""
# # #     best = None
# # #     for r in responses:
# # #         if r.get("status", {}).get("message") != "Success":
# # #             continue
# # #         for fare in r.get("onwardJourneyFareList") or []:
# # #             price = fare.get("finalPriceAfterDiscount")
# # #             if price is None:
# # #                 continue
# # #             if best is None or price < best["total_fare"]:
# # #                 best = {
# # #                     "total_fare": price,
# # #                     "base_fare": fare.get("initialPrice"),
# # #                     "discount_amount": fare.get("discountAmount"),
# # #                     "discount_percent": fare.get("discountPercent"),
# # #                     "fare_family": f"type_{fare.get('type')}" if fare.get("type") is not None else None,
# # #                 }
# # #     return best


# # # def normalize_response(entry: dict, origin: str, dest: str, travel_date: str,
# # #                         adv: int, route_id: str, total_passengers: int, outcome: str = "ok"):
# # #     now_iso = datetime.now().astimezone().isoformat()
# # #     responses = entry.get("responses", [])
# # #     best = best_fare_from_responses(responses)

# # #     if best:
# # #         availability_status = "available"
# # #         no_flights_flag = False
# # #         data_quality = 80
# # #     elif outcome == "genuine_no_flights":
# # #         availability_status = "no_flights"
# # #         no_flights_flag = True
# # #         data_quality = 0
# # #     elif outcome == "blocked_after_retries":
# # #         availability_status = "blocked"
# # #         no_flights_flag = False
# # #         data_quality = 0
# # #     else:
# # #         availability_status = "not_collected"
# # #         no_flights_flag = False
# # #         data_quality = 0

# # #     record = {
# # #         "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
# # #         "collection_timestamp": now_iso,
# # #         "route_id": route_id,
# # #         "total_passengers": total_passengers,
# # #         "origin": origin,
# # #         "destination": dest,
# # #         "travel_date": travel_date,
# # #         "advance_purchase_days": adv,
# # #         "trip_type": "one_way",
# # #         "passenger_count": 1,
# # #         "cabin": "economy",
# # #         "stops": None,
# # #         "airline_code": "IX",
# # #         "airline_name": "Air India Express",
# # #         "flight_number": None,
# # #         "departure_time": None,
# # #         "arrival_time": None,
# # #         "duration_minutes": None,
# # #         "fare_family": best.get("fare_family") if best else None,
# # #         "base_fare": best.get("base_fare") if best else None,
# # #         "taxes": None,
# # #         "mandatory_fees": None,
# # #         "total_fare": best.get("total_fare") if best else None,
# # #         "discount_amount": best.get("discount_amount") if best else None,
# # #         "discount_percent": best.get("discount_percent") if best else None,
# # #         "currency": "INR",
# # #         "availability_status": availability_status,
# # #         "seats_available": None,
# # #         "source": "Air India Express",
# # #         "source_type": "airline",
# # #         "data_quality_score": data_quality,
# # #         "no_flights": no_flights_flag,
# # #         "sold_out": False,
# # #         "scrape_outcome": outcome,
# # #     }
# # #     return sanitize_record(record)


# # # # ---------------------------
# # # # BATCH RUNNER
# # # # ---------------------------
# # # async def run_batch_scrape(headless: bool = True):
# # #     today = datetime.now()
# # #     normalized_all = []
# # #     total = len(ROUTES) * len(ADVANCE_WINDOWS)
# # #     print(f"Planned requests: {total} ({len(ROUTES)} routes x {len(ADVANCE_WINDOWS)} date windows)")

# # #     homepage = "https://www.airindiaexpress.com/"
# # #     if not robots_allowed(homepage):
# # #         print(f"  [!] Robots policy disallows {homepage} -- aborting")
# # #         return []

# # #     count = 0
# # #     run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# # #     async with async_playwright() as p:
# # #         browser = await p.chromium.launch(
# # #             headless=headless,
# # #             args=["--headless=new"] if headless else [],
# # #         )

# # #         for origin, dest, route_id, pax in ROUTES:
# # #             windows = [
# # #                 (adv, (today + timedelta(days=adv)).strftime("%Y-%m-%d"))
# # #                 for adv in ADVANCE_WINDOWS
# # #             ]
# # #             print(f"[{count + 1}-{count + len(windows)}/{total}] {route_id} | {len(windows)} windows ...")
# # #             date_list = [d for _, d in windows]
# # #             window_results, window_outcomes = await scrape_route(origin, dest, date_list, browser)

# # #             for adv, travel_date in windows:
# # #                 count += 1
# # #                 entry = window_results.get(travel_date, {"responses": []})
# # #                 outcome = window_outcomes.get(travel_date, "ok")
# # #                 normalized_all.append(
# # #                     normalize_response(entry, origin, dest, travel_date, adv, route_id, pax, outcome)
# # #                 )
# # #                 has_data = any(r.get("onwardJourneyFareList") for r in entry.get("responses", []))
# # #                 status = "OK" if has_data else outcome
# # #                 print(f"  [{status}] T+{adv} | {travel_date}")

# # #             await asyncio.sleep(DELAY_BETWEEN_ROUTES)

# # #         await browser.close()

# # #     config = {
# # #         "airline": "Air India Express",
# # #         "run_timestamp": datetime.now().isoformat(),
# # #         "advance_windows": ADVANCE_WINDOWS,
# # #         "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
# # #         "routes": normalized_all,
# # #     }

# # #     out_path = OUTPUT_DIR / f"airindiaexpress_top_24_routes_{run_stamp}.json"
# # #     with open(out_path, "w", encoding="utf-8") as f:
# # #         json.dump(config, f, indent=2, ensure_ascii=False)

# # #     print(f"\nDone. Processed {total} route windows.")
# # #     print(f"Normalized records: {len(normalized_all)}")
# # #     print(f"Saved: {out_path}")
# # #     return normalized_all


# # # # ---------------------------
# # # # SINGLE-ROUTE TEST
# # # # ---------------------------
# # # async def test_single():
# # #     async with async_playwright() as p:
# # #         browser = await p.chromium.launch(headless=True, args=["--headless=new"])
# # #         captured, outcome = await scrape_single_date("DEL", "BOM", "2026-09-06", browser)
# # #         print(f"outcome={outcome}")
# # #         rec = normalize_response(captured, "DEL", "BOM", "2026-09-06", 1, "DELHI-MUMBAI", 4029444, outcome)

# # #         print(f"\nNormalized record:\n")
# # #         print(f"  total_fare: {rec.get('total_fare')}  |  base_fare: {rec.get('base_fare')}  |  "
# # #               f"discount: {rec.get('discount_percent')}%  |  status: {rec.get('availability_status')}")

# # #         stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# # #         raw_path = OUTPUT_DIR / f"aix_raw_test_{stamp}.json"
# # #         with open(raw_path, "w", encoding="utf-8") as f:
# # #             json.dump(captured, f, indent=2, ensure_ascii=False)
# # #         norm_path = OUTPUT_DIR / f"aix_normalized_test_{stamp}.json"
# # #         with open(norm_path, "w", encoding="utf-8") as f:
# # #             json.dump(rec, f, indent=2, ensure_ascii=False)

# # #         print(f"\nRaw saved to:        {raw_path}")
# # #         print(f"Normalized saved to: {norm_path}")
# # #         await browser.close()


# # # if __name__ == "__main__":
# # #     import sys
# # #     if len(sys.argv) > 1 and sys.argv[1] == "test":
# # #         asyncio.run(test_single())
# # #     else:
# # #         asyncio.run(run_batch_scrape(headless=True))
# # import asyncio
# # import json
# # import uuid
# # from datetime import datetime, timedelta, timezone
# # from pathlib import Path
# # from urllib.parse import urlparse
# # from urllib.error import HTTPError
# # from urllib.request import Request, urlopen
# # from urllib.robotparser import RobotFileParser

# # from playwright.async_api import async_playwright

# # # ---------------------------
# # # CONFIG
# # # ---------------------------

# # ADVANCE_WINDOWS = [1, 7, 15, 30]

# # DELAY_BETWEEN_ROUTES = 15
# # CONSECUTIVE_FAILURE_BACKOFF = 60
# # MAX_CONSECUTIVE_FAILURES = 5
# # MAX_RETRIES_PER_DATE = 3
# # RETRY_BACKOFF_BASE = 20

# # OUTPUT_DIR = Path("airindiaexpress")
# # OUTPUT_DIR.mkdir(exist_ok=True)
# # SCREENSHOT_DIR = OUTPUT_DIR / "ss"
# # SCREENSHOT_DIR.mkdir(exist_ok=True)

# # USER_AGENT = (
# #     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
# #     "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# # )

# # FSA_URL_TEMPLATE = (
# #     "https://www.airindiaexpress.com/flight-availability?"
# #     "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
# # )

# # FARE_API_PATH = "search-availability-for-discount"

# # ROBOTS_CACHE = {}


# # def robots_allowed(url: str) -> bool:
# #     """
# #     Mirrors the working logic from the earlier AIX scraper: if robots.txt
# #     can't be fetched/parsed (network hiccup, transient 4xx, etc.), we treat
# #     the URL as allowed rather than silently blocking every request. This
# #     fixed the 'Robots policy disallows' false negative caused by
# #     RobotFileParser().read() failing silently.
# #     """
# #     parsed = urlparse(url)
# #     robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

# #     if robots_url in ROBOTS_CACHE:
# #         return ROBOTS_CACHE[robots_url].can_fetch("*", url)

# #     parser = RobotFileParser()
# #     parser.set_url(robots_url)
# #     try:
# #         request = Request(robots_url, headers={"User-Agent": USER_AGENT})
# #         with urlopen(request, timeout=15) as response:
# #             content = response.read().decode("utf-8", errors="replace")
# #         parser.parse(content.splitlines())
# #     except HTTPError as exc:
# #         if 400 <= exc.code <= 499 and exc.code != 429:
# #             print(f"  [i] robots.txt returned HTTP {exc.code}; treating as allowed")
# #             return True
# #         print(f"  [!] Could not read {robots_url}: HTTP {exc.code}; treating as allowed")
# #         return True
# #     except Exception as exc:
# #         print(f"  [!] Could not read {robots_url}: {exc}; treating as allowed")
# #         return True

# #     ROBOTS_CACHE[robots_url] = parser
# #     return parser.can_fetch("*", url)


# # CITY_TO_IATA = {
# #     "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "HYDERABAD": "HYD",
# #     "KOLKATA": "CCU", "PUNE": "PNQ", "GOA": "GOX", "AHMEDABAD": "AMD",
# #     "CHENNAI": "MAA", "SRINAGAR": "SXR", "GUWAHATI": "GAU", "PATNA": "PAT",
# #     "LUCKNOW": "LKO", "KOCHI": "COK",
# # }

# # PRIORITY_ROUTES = [
# #     ("DELHI", "MUMBAI", 4029444), ("BENGALURU", "DELHI", 2885936),
# #     ("BENGALURU", "MUMBAI", 2476421), ("DELHI", "HYDERABAD", 1862287),
# #     ("DELHI", "KOLKATA", 1778985), ("DELHI", "PUNE", 1704284),
# #     ("GOA", "MUMBAI", 1495328), ("AHMEDABAD", "DELHI", 1402813),
# #     ("DELHI", "GOA", 1352032), ("CHENNAI", "MUMBAI", 1312448),
# #     ("HYDERABAD", "MUMBAI", 1285881), ("KOLKATA", "MUMBAI", 1281897),
# #     ("CHENNAI", "DELHI", 1277274), ("BENGALURU", "HYDERABAD", 1217734),
# #     ("AHMEDABAD", "MUMBAI", 1215086), ("BENGALURU", "KOLKATA", 1204113),
# #     ("DELHI", "SRINAGAR", 1141145), ("BENGALURU", "PUNE", 1079353),
# #     ("DELHI", "GUWAHATI", 938099), ("DELHI", "PATNA", 908354),
# #     ("BENGALURU", "GOA", 875214), ("BENGALURU", "CHENNAI", 872523),
# #     ("DELHI", "LUCKNOW", 854555), ("KOCHI", "MUMBAI", 805813),
# # ]


# # def build_routes():
# #     routes = []
# #     for o_city, d_city, pax in PRIORITY_ROUTES:
# #         o_code = CITY_TO_IATA.get(o_city, o_city[:3])
# #         d_code = CITY_TO_IATA.get(d_city, d_city[:3])
# #         route_id = f"{o_city}-{d_city}"
# #         routes.append((o_code, d_code, route_id, pax))
# #     return routes


# # ROUTES = build_routes()


# # # ---------------------------
# # # NULL SANITIZER
# # # ---------------------------
# # NUMERIC_FIELDS = {
# #     "total_passengers", "advance_purchase_days", "passenger_count",
# #     "stops", "duration_minutes", "base_fare", "taxes",
# #     "mandatory_fees", "total_fare", "seats_available",
# #     "data_quality_score", "discount_amount", "discount_percent",
# #     "initial_price",
# # }
# # STRING_FIELDS = {
# #     "route_id", "origin", "destination", "travel_date", "trip_type",
# #     "cabin", "airline_code", "airline_name", "flight_number",
# #     "departure_time", "arrival_time", "fare_family", "currency",
# #     "availability_status", "source", "source_type", "scrape_outcome",
# # }
# # BOOL_FIELDS = {"no_flights", "sold_out"}


# # def sanitize_record(record: dict) -> dict:
# #     clean = dict(record)
# #     for key, value in clean.items():
# #         if value is not None:
# #             continue
# #         if key in NUMERIC_FIELDS:
# #             clean[key] = 0
# #         elif key in BOOL_FIELDS:
# #             clean[key] = False
# #         elif key in STRING_FIELDS:
# #             clean[key] = "N/A"
# #         else:
# #             clean[key] = "N/A"
# #     if "scrape_outcome" not in clean:
# #         clean["scrape_outcome"] = "ok"
# #     return clean


# # # ---------------------------
# # # CORE SCRAPE FUNCTION
# # # ---------------------------
# # async def scrape_single_date(origin: str, dest: str, travel_date: str, browser):
# #     captured = {"responses": []}

# #     async def handle_response(response, captured=captured):
# #         if response.status != 200:
# #             return
# #         if FARE_API_PATH not in response.url or response.request.method != "POST":
# #             return
# #         try:
# #             body = await response.json()
# #             captured["responses"].append(body)
# #         except Exception:
# #             pass

# #     search_url = FSA_URL_TEMPLATE.format(origin=origin, destination=dest, date=travel_date)
# #     if not robots_allowed(search_url):
# #         print(f"  [!] Robots policy disallows {search_url}")
# #         return captured, "robots_disallowed"

# #     context = await browser.new_context(
# #         user_agent=USER_AGENT,
# #         viewport={"width": 1366, "height": 768},
# #         locale="en-IN",
# #     )
# #     page = await context.new_page()
# #     page.on("response", handle_response)

# #     outcome = "ok"
# #     try:
# #         resp = await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
# #         status = resp.status if resp is not None else None
# #         print(f"  [i] page load status={status} for {origin}->{dest} {travel_date}")

# #         deadline = asyncio.get_event_loop().time() + 15
# #         while asyncio.get_event_loop().time() < deadline:
# #             if captured["responses"]:
# #                 break
# #             await page.wait_for_timeout(1000)

# #         if not captured["responses"]:
# #             try:
# #                 no_flights_visible = await page.locator(
# #                     "text=/sorry.*no.*flight/i, text=/no flights? found/i"
# #                 ).first.is_visible(timeout=1000)
# #             except Exception:
# #                 no_flights_visible = False

# #             if no_flights_visible:
# #                 outcome = "genuine_no_flights"
# #             else:
# #                 try:
# #                     rate_limited = await page.locator(
# #                         "text=/take a break/i, text=/tried a few times/i"
# #                     ).first.is_visible(timeout=1000)
# #                 except Exception:
# #                     rate_limited = False
# #                 outcome = "rate_limited" if rate_limited else "no_api_captured"

# #                 shot_path = SCREENSHOT_DIR / f"debug_{origin}_{dest}_{travel_date}_{datetime.now().strftime('%H%M%S')}.png"
# #                 try:
# #                     await page.screenshot(path=str(shot_path), full_page=True)
# #                     print(f"  [!] {outcome} -- screenshot saved: {shot_path}")
# #                 except Exception:
# #                     pass
# #     except Exception as e:
# #         print(f"  [!] Navigation error for {origin}->{dest} {travel_date}: {e}")
# #         outcome = "nav_error"
# #     finally:
# #         page.remove_listener("response", handle_response)
# #         await context.close()

# #     return captured, outcome


# # async def scrape_date_with_retries(origin: str, dest: str, travel_date: str, browser):
# #     last_outcome = "not_attempted"
# #     for attempt in range(1, MAX_RETRIES_PER_DATE + 1):
# #         captured, outcome = await scrape_single_date(origin, dest, travel_date, browser)
# #         last_outcome = outcome

# #         has_valid_fares = any(
# #             r.get("status", {}).get("message") == "Success" and r.get("onwardJourneyFareList")
# #             for r in captured["responses"]
# #         )

# #         if has_valid_fares or outcome == "genuine_no_flights":
# #             if attempt > 1:
# #                 print(f"  [i] Resolved after {attempt} attempt(s): outcome={outcome}")
# #             return captured, outcome

# #         if outcome == "rate_limited":
# #             backoff = RETRY_BACKOFF_BASE * attempt * 2
# #         else:
# #             backoff = RETRY_BACKOFF_BASE * attempt

# #         if attempt < MAX_RETRIES_PER_DATE:
# #             print(f"  [!] Attempt {attempt}/{MAX_RETRIES_PER_DATE} failed ({outcome}) "
# #                   f"-- retrying in {backoff}s")
# #             await asyncio.sleep(backoff)

# #     print(f"  [!] Exhausted {MAX_RETRIES_PER_DATE} attempts for {origin}->{dest} {travel_date} "
# #           f"-- recording as blocked (last outcome: {last_outcome})")
# #     return {"responses": []}, "blocked_after_retries"


# # async def scrape_route(origin: str, dest: str, travel_dates: list, browser):
# #     results = {}
# #     outcomes = {}
# #     consecutive_failures = 0

# #     for travel_date in travel_dates:
# #         if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
# #             print(f"  [!] {consecutive_failures} consecutive failures -- cooling down {CONSECUTIVE_FAILURE_BACKOFF}s")
# #             await asyncio.sleep(CONSECUTIVE_FAILURE_BACKOFF)
# #             consecutive_failures = 0

# #         captured, outcome = await scrape_date_with_retries(origin, dest, travel_date, browser)
# #         results[travel_date] = captured
# #         outcomes[travel_date] = outcome

# #         has_valid_fares = any(
# #             r.get("status", {}).get("message") == "Success" and r.get("onwardJourneyFareList")
# #             for r in captured["responses"]
# #         )

# #         if outcome in ("ok", "genuine_no_flights") or has_valid_fares:
# #             consecutive_failures = 0
# #         else:
# #             consecutive_failures += 1

# #         await asyncio.sleep(RETRY_BACKOFF_BASE / 2)

# #     return results, outcomes


# # # ---------------------------
# # # NORMALIZATION
# # # ---------------------------
# # def best_fare_from_responses(responses: list):
# #     best = None
# #     for r in responses:
# #         if r.get("status", {}).get("message") != "Success":
# #             continue
# #         for fare in r.get("onwardJourneyFareList") or []:
# #             price = fare.get("finalPriceAfterDiscount")
# #             if price is None:
# #                 continue
# #             if best is None or price < best["total_fare"]:
# #                 best = {
# #                     "total_fare": price,
# #                     "base_fare": fare.get("initialPrice"),
# #                     "discount_amount": fare.get("discountAmount"),
# #                     "discount_percent": fare.get("discountPercent"),
# #                     "fare_family": f"type_{fare.get('type')}" if fare.get("type") is not None else None,
# #                 }
# #     return best


# # def normalize_response(entry: dict, origin: str, dest: str, travel_date: str,
# #                         adv: int, route_id: str, total_passengers: int, outcome: str = "ok"):
# #     now_iso = datetime.now().astimezone().isoformat()
# #     responses = entry.get("responses", [])
# #     best = best_fare_from_responses(responses)

# #     if best:
# #         availability_status = "available"
# #         no_flights_flag = False
# #         data_quality = 80
# #     elif outcome == "genuine_no_flights":
# #         availability_status = "no_flights"
# #         no_flights_flag = True
# #         data_quality = 0
# #     elif outcome == "blocked_after_retries":
# #         availability_status = "blocked"
# #         no_flights_flag = False
# #         data_quality = 0
# #     else:
# #         availability_status = "not_collected"
# #         no_flights_flag = False
# #         data_quality = 0

# #     record = {
# #         "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
# #         "collection_timestamp": now_iso,
# #         "route_id": route_id,
# #         "total_passengers": total_passengers,
# #         "origin": origin,
# #         "destination": dest,
# #         "travel_date": travel_date,
# #         "advance_purchase_days": adv,
# #         "trip_type": "one_way",
# #         "passenger_count": 1,
# #         "cabin": "economy",
# #         "stops": None,
# #         "airline_code": "IX",
# #         "airline_name": "Air India Express",
# #         "flight_number": None,
# #         "departure_time": None,
# #         "arrival_time": None,
# #         "duration_minutes": None,
# #         "fare_family": best.get("fare_family") if best else None,
# #         "base_fare": best.get("base_fare") if best else None,
# #         "taxes": None,
# #         "mandatory_fees": None,
# #         "total_fare": best.get("total_fare") if best else None,
# #         "discount_amount": best.get("discount_amount") if best else None,
# #         "discount_percent": best.get("discount_percent") if best else None,
# #         "currency": "INR",
# #         "availability_status": availability_status,
# #         "seats_available": None,
# #         "source": "Air India Express",
# #         "source_type": "airline",
# #         "data_quality_score": data_quality,
# #         "no_flights": no_flights_flag,
# #         "sold_out": False,
# #         "scrape_outcome": outcome,
# #     }
# #     return sanitize_record(record)


# # # ---------------------------
# # # BATCH RUNNER
# # # ---------------------------
# # async def run_batch_scrape(headless: bool = True):
# #     today = datetime.now()
# #     normalized_all = []
# #     total = len(ROUTES) * len(ADVANCE_WINDOWS)
# #     print(f"Planned requests: {total} ({len(ROUTES)} routes x {len(ADVANCE_WINDOWS)} date windows)")

# #     homepage = "https://www.airindiaexpress.com/"
# #     if not robots_allowed(homepage):
# #         print(f"  [!] Robots policy disallows {homepage} -- aborting")
# #         return []

# #     count = 0
# #     run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# #     async with async_playwright() as p:
# #         browser = await p.chromium.launch(
# #             headless=headless,
# #             args=["--headless=new"] if headless else [],
# #         )

# #         for origin, dest, route_id, pax in ROUTES:
# #             windows = [
# #                 (adv, (today + timedelta(days=adv)).strftime("%Y-%m-%d"))
# #                 for adv in ADVANCE_WINDOWS
# #             ]
# #             print(f"[{count + 1}-{count + len(windows)}/{total}] {route_id} | {len(windows)} windows ...")
# #             date_list = [d for _, d in windows]
# #             window_results, window_outcomes = await scrape_route(origin, dest, date_list, browser)

# #             for adv, travel_date in windows:
# #                 count += 1
# #                 entry = window_results.get(travel_date, {"responses": []})
# #                 outcome = window_outcomes.get(travel_date, "ok")
# #                 normalized_all.append(
# #                     normalize_response(entry, origin, dest, travel_date, adv, route_id, pax, outcome)
# #                 )
# #                 has_data = any(r.get("onwardJourneyFareList") for r in entry.get("responses", []))
# #                 status = "OK" if has_data else outcome
# #                 print(f"  [{status}] T+{adv} | {travel_date}")

# #             await asyncio.sleep(DELAY_BETWEEN_ROUTES)

# #         await browser.close()

# #     config = {
# #         "airline": "Air India Express",
# #         "run_timestamp": datetime.now().isoformat(),
# #         "advance_windows": ADVANCE_WINDOWS,
# #         "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
# #         "routes": normalized_all,
# #     }

# #     out_path = OUTPUT_DIR / f"airindiaexpress_top_24_routes_{run_stamp}.json"
# #     with open(out_path, "w", encoding="utf-8") as f:
# #         json.dump(config, f, indent=2, ensure_ascii=False)

# #     print(f"\nDone. Processed {total} route windows.")
# #     print(f"Normalized records: {len(normalized_all)}")
# #     print(f"Saved: {out_path}")
# #     return normalized_all


# # # ---------------------------
# # # SINGLE-ROUTE TEST
# # # ---------------------------
# # async def test_single():
# #     async with async_playwright() as p:
# #         browser = await p.chromium.launch(headless=True, args=["--headless=new"])
# #         captured, outcome = await scrape_single_date("DEL", "BOM", "2026-09-06", browser)
# #         print(f"outcome={outcome}")
# #         rec = normalize_response(captured, "DEL", "BOM", "2026-09-06", 1, "DELHI-MUMBAI", 4029444, outcome)

# #         print(f"\nNormalized record:\n")
# #         print(f"  total_fare: {rec.get('total_fare')}  |  base_fare: {rec.get('base_fare')}  |  "
# #               f"discount: {rec.get('discount_percent')}%  |  status: {rec.get('availability_status')}")

# #         stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# #         raw_path = OUTPUT_DIR / f"aix_raw_test_{stamp}.json"
# #         with open(raw_path, "w", encoding="utf-8") as f:
# #             json.dump(captured, f, indent=2, ensure_ascii=False)
# #         norm_path = OUTPUT_DIR / f"aix_normalized_test_{stamp}.json"
# #         with open(norm_path, "w", encoding="utf-8") as f:
# #             json.dump(rec, f, indent=2, ensure_ascii=False)

# #         print(f"\nRaw saved to:        {raw_path}")
# #         print(f"Normalized saved to: {norm_path}")
# #         await browser.close()


# # if __name__ == "__main__":
# #     import sys
# #     if len(sys.argv) > 1 and sys.argv[1] == "test":
# #         asyncio.run(test_single())
# #     else:
# #         asyncio.run(run_batch_scrape(headless=True))
# import asyncio
# import json
# import re
# import uuid
# from datetime import datetime, timedelta, timezone
# from pathlib import Path
# from urllib.parse import urlparse
# from urllib.error import HTTPError
# from urllib.request import Request, urlopen
# from urllib.robotparser import RobotFileParser
# from xml.etree import ElementTree

# from playwright.async_api import async_playwright

# # ---------------------------
# # CONFIG
# # ---------------------------

# ADVANCE_WINDOWS = [1, 7, 15, 30]
# USER_AGENT = "VAYUSETU-Bot"

# BASE_URL = "https://flights.airindiaexpress.com"
# ROBOTS_URL = f"{BASE_URL}/robots.txt"
# SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"

# OUTPUT_DIR = Path("airindiaexpress")
# OUTPUT_DIR.mkdir(exist_ok=True)
# SCREENSHOT_DIR = OUTPUT_DIR / "ss"
# SCREENSHOT_DIR.mkdir(exist_ok=True)

# CITY_TO_IATA = {
#     "DELHI": "DEL", "MUMBAI": "BOM", "BENGALURU": "BLR", "HYDERABAD": "HYD",
#     "KOLKATA": "CCU", "PUNE": "PNQ", "GOA": "GOX", "AHMEDABAD": "AMD",
#     "CHENNAI": "MAA", "SRINAGAR": "SXR", "GUWAHATI": "GAU", "PATNA": "PAT",
#     "LUCKNOW": "LKO", "KOCHI": "COK",
# }

# CITY_TO_SLUG = {
#     "DELHI": "delhi", "MUMBAI": "mumbai", "BENGALURU": "bengaluru",
#     "HYDERABAD": "hyderabad", "KOLKATA": "kolkata", "PUNE": "pune", "GOA": "goa",
#     "AHMEDABAD": "ahmedabad", "CHENNAI": "chennai", "SRINAGAR": "srinagar",
#     "GUWAHATI": "guwahati", "PATNA": "patna", "LUCKNOW": "lucknow", "KOCHI": "kochi",
# }

# PRIORITY_ROUTES = [
#     ("DELHI", "MUMBAI", 4029444), ("BENGALURU", "DELHI", 2885936),
#     ("BENGALURU", "MUMBAI", 2476421), ("DELHI", "HYDERABAD", 1862287),
#     ("DELHI", "KOLKATA", 1778985), ("DELHI", "PUNE", 1704284),
#     ("GOA", "MUMBAI", 1495328), ("AHMEDABAD", "DELHI", 1402813),
#     ("DELHI", "GOA", 1352032), ("CHENNAI", "MUMBAI", 1312448),
#     ("HYDERABAD", "MUMBAI", 1285881), ("KOLKATA", "MUMBAI", 1281897),
#     ("CHENNAI", "DELHI", 1277274), ("BENGALURU", "HYDERABAD", 1217734),
#     ("AHMEDABAD", "MUMBAI", 1215086), ("BENGALURU", "KOLKATA", 1204113),
#     ("DELHI", "SRINAGAR", 1141145), ("BENGALURU", "PUNE", 1079353),
#     ("DELHI", "GUWAHATI", 938099), ("DELHI", "PATNA", 908354),
#     ("BENGALURU", "GOA", 875214), ("BENGALURU", "CHENNAI", 872523),
#     ("DELHI", "LUCKNOW", 854555), ("KOCHI", "MUMBAI", 805813),
# ]

# DELAY_BETWEEN_ROUTES = 5
# RETRY_BACKOFF_BASE = 15
# MAX_RETRIES = 2


# # ---------------------------
# # ROBOTS.TXT
# # ---------------------------
# def fetch_url_text(url: str, timeout: int = 20) -> str:
#     request = Request(url, headers={"User-Agent": USER_AGENT})
#     with urlopen(request, timeout=timeout) as response:
#         return response.read().decode("utf-8", errors="replace")


# def robots_allowed(url: str) -> bool:
#     try:
#         content = fetch_url_text(ROBOTS_URL)
#     except HTTPError as exc:
#         if 400 <= exc.code <= 499 and exc.code != 429:
#             print(f"  [i] robots.txt HTTP {exc.code}; treating as allowed")
#             return True
#         print(f"  [!] Could not read {ROBOTS_URL}: HTTP {exc.code}; treating as allowed")
#         return True
#     except Exception as exc:
#         print(f"  [!] Could not read {ROBOTS_URL}: {exc}; treating as allowed")
#         return True

#     parser = RobotFileParser()
#     parser.set_url(ROBOTS_URL)
#     parser.parse(content.splitlines())
#     return parser.can_fetch(USER_AGENT, url)


# # ---------------------------
# # SITEMAP DISCOVERY
# # ---------------------------
# def parse_sitemap_urls(xml_text: str) -> list:
#     """Handles both a sitemap index (<sitemapindex>) and a leaf urlset (<urlset>)."""
#     try:
#         root = ElementTree.fromstring(xml_text)
#     except ElementTree.ParseError as exc:
#         print(f"  [!] Failed to parse sitemap XML: {exc}")
#         return []

#     ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
#     tag = root.tag.lower()

#     if tag.endswith("sitemapindex"):
#         return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
#     if tag.endswith("urlset"):
#         return [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
#     return []


# def discover_route_url_map(routes: list) -> dict:
#     """
#     Fetches the sitemap index, then each child sitemap, collecting every
#     <loc> that looks like a city-to-city flight route page. Returns a dict
#     mapping (origin_slug, dest_slug) -> full URL, built ONLY from what the
#     sitemap actually lists -- never guessed/constructed.
#     """
#     wanted_slugs = set()
#     for o_city, d_city, _ in routes:
#         o_slug = CITY_TO_SLUG.get(o_city)
#         d_slug = CITY_TO_SLUG.get(d_city)
#         if o_slug and d_slug:
#             wanted_slugs.add((o_slug, d_slug))

#     route_url_map = {}
#     route_pattern = re.compile(r"/([a-z-]+)-to-([a-z-]+)-flights", re.IGNORECASE)

#     try:
#         index_xml = fetch_url_text(SITEMAP_INDEX_URL)
#     except Exception as exc:
#         print(f"  [!] Could not fetch sitemap index {SITEMAP_INDEX_URL}: {exc}")
#         return route_url_map

#     child_sitemaps = parse_sitemap_urls(index_xml)
#     if not child_sitemaps:
#         # index might itself be a flat urlset
#         child_sitemaps = [SITEMAP_INDEX_URL]

#     print(f"  [i] Sitemap index lists {len(child_sitemaps)} child sitemap(s)")

#     for sitemap_url in child_sitemaps:
#         if not robots_allowed(sitemap_url):
#             print(f"  [!] Robots disallows sitemap {sitemap_url}; skipping")
#             continue
#         try:
#             child_xml = fetch_url_text(sitemap_url)
#         except Exception as exc:
#             print(f"  [!] Could not fetch {sitemap_url}: {exc}")
#             continue

#         urls = parse_sitemap_urls(child_xml)
#         for url in urls:
#             match = route_pattern.search(url)
#             if not match:
#                 continue
#             o_slug, d_slug = match.group(1).lower(), match.group(2).lower()
#             if (o_slug, d_slug) in wanted_slugs:
#                 route_url_map[(o_slug, d_slug)] = url

#         if len(route_url_map) == len(wanted_slugs):
#             break  # found everything we need, stop early

#     print(f"  [i] Matched {len(route_url_map)}/{len(wanted_slugs)} priority routes in sitemap")
#     return route_url_map


# # ---------------------------
# # NULL SANITIZER
# # ---------------------------
# NUMERIC_FIELDS = {
#     "total_passengers", "advance_purchase_days", "passenger_count",
#     "stops", "duration_minutes", "base_fare", "taxes",
#     "mandatory_fees", "total_fare", "seats_available", "data_quality_score",
# }
# STRING_FIELDS = {
#     "route_id", "origin", "destination", "travel_date", "trip_type",
#     "cabin", "airline_code", "airline_name", "flight_number",
#     "departure_time", "arrival_time", "fare_family", "currency",
#     "availability_status", "source", "source_type", "source_url", "scrape_outcome",
# }
# BOOL_FIELDS = {"no_flights", "sold_out"}


# def sanitize_record(record: dict) -> dict:
#     clean = dict(record)
#     for key, value in clean.items():
#         if value is not None:
#             continue
#         if key in NUMERIC_FIELDS:
#             clean[key] = 0
#         elif key in BOOL_FIELDS:
#             clean[key] = False
#         elif key in STRING_FIELDS:
#             clean[key] = "N/A"
#         else:
#             clean[key] = "N/A"
#     if "scrape_outcome" not in clean:
#         clean["scrape_outcome"] = "ok"
#     return clean


# # ---------------------------
# # FARE PARSING (text-based, from the sitemap-listed route page)
# # ---------------------------
# def parse_fares(text, origin, destination):
#     pattern = re.compile(
#         rf"{origin}[–-]{destination},\s+([A-Za-z]{{3}},\s+[A-Za-z]{{3}}\s+\d{{1,2}}\s+\d{{4}}):\s+From\s+₹([\d,]+)",
#         re.IGNORECASE,
#     )
#     fares = {}
#     for date_text, amount in pattern.findall(text):
#         try:
#             date = datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")
#             fares[date] = float(amount.replace(",", ""))
#         except ValueError:
#             continue
#     return fares


# async def collect_route_fares(page, route_url, origin, destination, target_dates):
#     fares = {}
#     resp = await page.goto(route_url, wait_until="domcontentloaded", timeout=60000)
#     if not resp or resp.status != 200:
#         return fares, f"http_{resp.status if resp else 'none'}"

#     body = await page.locator("body").inner_text()
#     fares.update(parse_fares(body, origin, destination))

#     missing_months = sorted({
#         datetime.strptime(d, "%Y-%m-%d").strftime("%b %Y")
#         for d in target_dates if d not in fares
#     })
#     for month_label in missing_months:
#         try:
#             carousel = page.locator("section[aria-label='Month selection carousel']")
#             month = carousel.get_by_text(month_label, exact=True)
#             if await month.count() == 0:
#                 continue
#             await month.first.click(timeout=3000)
#             await page.wait_for_timeout(1200)
#             body = await page.locator("body").inner_text()
#             fares.update(parse_fares(body, origin, destination))
#         except Exception:
#             break

#     return fares, None


# # ---------------------------
# # NORMALIZATION
# # ---------------------------
# def normalize_record(route_id, passengers, origin, destination, travel_date,
#                       advance_days, source_url, fare, error):
#     available = fare is not None
#     record = {
#         "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
#         "collection_timestamp": datetime.now().astimezone().isoformat(),
#         "route_id": route_id,
#         "total_passengers": passengers,
#         "origin": origin,
#         "destination": destination,
#         "travel_date": travel_date,
#         "advance_purchase_days": advance_days,
#         "trip_type": "one_way",
#         "passenger_count": 1,
#         "cabin": "economy",
#         "stops": None,
#         "airline_code": "IX",
#         "airline_name": "Air India Express",
#         "flight_number": None,
#         "departure_time": None,
#         "arrival_time": None,
#         "duration_minutes": None,
#         "fare_family": "Economy" if available else None,
#         "base_fare": None,
#         "taxes": None,
#         "mandatory_fees": None,
#         "total_fare": fare,
#         "currency": "INR",
#         "availability_status": "available" if available else ("collection_error" if error else "not_published"),
#         "seats_available": None,
#         "source": "Air India Express",
#         "source_type": "sitemap_listed_route_page",
#         "source_url": source_url,
#         "data_quality_score": 70 if available else 0,
#         "no_flights": False if available else None,
#         "sold_out": None,
#         "scrape_outcome": "ok" if available else (error or "not_published"),
#     }
#     return sanitize_record(record)


# # ---------------------------
# # BATCH RUNNER
# # ---------------------------
# async def run_batch_scrape(headless: bool = True):
#     print("[1/3] Checking robots.txt and discovering route URLs from sitemap...")

#     if not robots_allowed(BASE_URL):
#         print(f"  [!] Robots policy disallows {BASE_URL} -- aborting")
#         return []

#     route_url_map = discover_route_url_map(PRIORITY_ROUTES)
#     if not route_url_map:
#         print("  [!] No matching route URLs found in sitemap -- aborting")
#         return []

#     today = datetime.now()
#     windows = [(d, (today + timedelta(days=d)).strftime("%Y-%m-%d")) for d in ADVANCE_WINDOWS]
#     target_dates = [d for _, d in windows]

#     normalized_all = []
#     run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

#     print(f"[2/3] Scraping {len(route_url_map)} route page(s), {len(ADVANCE_WINDOWS)} windows each...")

#     async with async_playwright() as playwright:
#         browser = await playwright.chromium.launch(headless=headless)
#         page = await browser.new_page(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})

#         for index, (o_city, d_city, passengers) in enumerate(PRIORITY_ROUTES, 1):
#             o_slug = CITY_TO_SLUG.get(o_city)
#             d_slug = CITY_TO_SLUG.get(d_city)
#             route_url = route_url_map.get((o_slug, d_slug))
#             route_id = f"{o_city}-{d_city}"

#             if not route_url:
#                 print(f"[{index}/{len(PRIORITY_ROUTES)}] {route_id} -- not in sitemap, skipping")
#                 for advance_days, travel_date in windows:
#                     normalized_all.append(normalize_record(
#                         route_id, passengers, CITY_TO_IATA[o_city], CITY_TO_IATA[d_city],
#                         travel_date, advance_days, None, None, "not_in_sitemap",
#                     ))
#                 continue

#             print(f"[{index}/{len(PRIORITY_ROUTES)}] {route_id} -> {route_url}")

#             fares, error = {}, None
#             for attempt in range(1, MAX_RETRIES + 1):
#                 fares, error = await collect_route_fares(
#                     page, route_url, CITY_TO_IATA[o_city], CITY_TO_IATA[d_city], target_dates
#                 )
#                 if fares or attempt == MAX_RETRIES:
#                     break
#                 backoff = RETRY_BACKOFF_BASE * attempt
#                 print(f"  [!] No fares captured, retrying in {backoff}s...")
#                 await asyncio.sleep(backoff)

#             for advance_days, travel_date in windows:
#                 fare = fares.get(travel_date)
#                 normalized_all.append(normalize_record(
#                     route_id, passengers, CITY_TO_IATA[o_city], CITY_TO_IATA[d_city],
#                     travel_date, advance_days, route_url, fare, error,
#                 ))

#             await asyncio.sleep(DELAY_BETWEEN_ROUTES)

#         await browser.close()

#     output = {
#         "airline": "Air India Express",
#         "base_url": BASE_URL,
#         "robots_url": ROBOTS_URL,
#         "sitemap_index": SITEMAP_INDEX_URL,
#         "run_timestamp": datetime.now().isoformat(),
#         "last_checked": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
#         "advance_windows": ADVANCE_WINDOWS,
#         "routes_matched_in_sitemap": len(route_url_map),
#         "routes_total_priority": len(PRIORITY_ROUTES),
#         "records": normalized_all,
#     }

#     print("[3/3] Saving output...")
#     out_path = OUTPUT_DIR / f"airindiaexpress_sitemap_routes_{run_stamp}.json"
#     with open(out_path, "w", encoding="utf-8") as f:
#         json.dump(output, f, indent=2, ensure_ascii=False)

#     print(f"\nDone. {len(normalized_all)} records written.")
#     print(f"Saved: {out_path}")
#     return normalized_all


# if __name__ == "__main__":
#     asyncio.run(run_batch_scrape(headless=True))


import asyncio
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from playwright.async_api import async_playwright

from common.routes import CITY_TO_IATA, PRIORITY_ROUTES
from common.output import write_output

ADVANCE_WINDOWS = [1, 7, 15, 30, 45]
USER_AGENT = "VAYUSETU-Bot"
BASE_URL = "https://flights.airindiaexpress.com"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SITEMAP_URL = f"{BASE_URL}/sitemap_index.xml"
OUTPUT_DIR = Path("airindiaexpress")
OUTPUT_DIR.mkdir(exist_ok=True)
SS_DIR = OUTPUT_DIR / "ss"
SS_DIR.mkdir(exist_ok=True)

# CITY_TO_IATA and PRIORITY_ROUTES imported from common.routes
CITY_TO_SLUG = {
    "DELHI": "delhi", "MUMBAI": "mumbai", "BENGALURU": "bengaluru",
    "HYDERABAD": "hyderabad", "KOLKATA": "kolkata", "PUNE": "pune", "GOA": "goa",
    "AHMEDABAD": "ahmedabad", "CHENNAI": "chennai", "SRINAGAR": "srinagar",
    "GUWAHATI": "guwahati", "PATNA": "patna", "LUCKNOW": "lucknow", "KOCHI": "kochi",
}


def robots_allowed(url):
    parser = RobotFileParser()
    parser.set_url(ROBOTS_URL)
    try:
        request = Request(ROBOTS_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
    except HTTPError as exc:
        # RFC 9309 section 2.3.1.4: 400-499 means robots.txt is
        # unavailable and the crawler may access resources.
        if 400 <= exc.code <= 499 and exc.code != 429:
            return True
        print(f"[!] Could not read {ROBOTS_URL}: HTTP {exc.code}")
        return False
    except Exception as exc:
        print(f"[!] Could not read {ROBOTS_URL}: {exc}")
        return False
    return parser.can_fetch(USER_AGENT, url)


def route_url(origin_city, destination_city):
    origin = CITY_TO_SLUG[origin_city]
    destination = CITY_TO_SLUG[destination_city]
    return f"{BASE_URL}/en-in/{origin}-to-{destination}-flights"


def parse_fares(text, origin, destination):
    pattern = re.compile(
        rf"{origin}[–-]{destination},\s+([A-Za-z]{{3}},\s+[A-Za-z]{{3}}\s+\d{{1,2}}\s+\d{{4}}):\s+From\s+₹([\d,]+)",
        re.IGNORECASE,
    )
    fares = {}
    for date_text, amount in pattern.findall(text):
        try:
            date = datetime.strptime(date_text, "%a, %b %d %Y").strftime("%Y-%m-%d")
            fares[date] = float(amount.replace(",", ""))
        except ValueError:
            continue
    return fares


def parse_duration(value):
    match = re.search(r"(?:(\d+)h)?\s*(?:(\d+)m)?", value or "")
    if not match or not any(match.groups()):
        return None
    return int(match.group(1) or 0) * 60 + int(match.group(2) or 0)


def parse_schedules(text, origin, destination):
    heading = re.search(r"Flight Schedule", text, re.IGNORECASE)
    if not heading:
        return []
    section = text[heading.end():]
    disclaimer = re.search(r"Disclaimer:\s*Flight timings", section, re.IGNORECASE)
    if disclaimer:
        section = section[:disclaimer.start()]
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    starts = [index for index, line in enumerate(lines) if re.fullmatch(r"(?:IX|I5)\s*\d+", line)]
    schedules = []
    for position, start in enumerate(starts):
        block = lines[start:(starts[position + 1] if position + 1 < len(starts) else len(lines))]
        try:
            origin_at = block.index(origin)
            destination_at = block.index(destination, origin_at + 1)
        except ValueError:
            continue
        times = [line for line in block[destination_at + 1:] if re.fullmatch(r"\d{1,2}:\d{2}(?:\s*\(\+1\))?", line)]
        duration = next((parse_duration(line) for line in block if re.fullmatch(r"(?:\d+h\s*)?(?:\d+m)", line)), None)
        if len(times) < 2:
            continue
        stop_label = block[origin_at + 1] if origin_at + 1 < destination_at else ""
        schedules.append({
            "flight_number": block[0].replace(" ", ""),
            "stops": 0 if "non-stop" in stop_label.lower() else None,
            "departure_clock": times[0].split()[0],
            "arrival_clock": times[1].split()[0],
            "arrival_next_day": "+1" in times[1],
            "duration_minutes": duration,
        })
    return schedules


async def collect_route(page, origin_city, destination_city, target_dates):
    origin = CITY_TO_IATA[origin_city]
    destination = CITY_TO_IATA[destination_city]
    url = route_url(origin_city, destination_city)
    if not robots_allowed(url):
        print(f"[!] Robots policy disallows {url}")
        return {}, [], url, "robots_disallowed"
    # AirTRFX keeps background requests open, so "networkidle" can time out even
    # after the published fare page is usable.  DOM readiness is sufficient for
    # reading the server-rendered fare calendar and schedule text.
    response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    if not response or response.status != 200:
        return {}, [], url, f"http_{response.status if response else 'none'}"

    fares = {}
    body = await page.locator("body").inner_text()
    fares.update(parse_fares(body, origin, destination))
    schedules = parse_schedules(body, origin, destination)

    missing_months = sorted({
        datetime.strptime(date, "%Y-%m-%d").strftime("%b %Y")
        for date in target_dates if date not in fares
    })
    for month_label in missing_months:
        try:
            carousel = page.locator("section[aria-label='Month selection carousel']")
            month = carousel.get_by_text(month_label, exact=True)
            if await month.count() == 0:
                continue
            await month.first.click(timeout=3000)
            await page.wait_for_timeout(1000)
            body = await page.locator("body").inner_text()
            fares.update(parse_fares(body, origin, destination))
        except Exception:
            break
    return fares, schedules, url, None


def normalized_record(route_id, passengers, origin, destination, travel_date, advance_days,
                      source_url, fare=None, schedule=None, error=None):
    schedule = schedule or {}
    departure_time = None
    arrival_time = None
    if schedule.get("departure_clock"):
        departure_time = f"{travel_date}T{schedule['departure_clock']}:00"
    if schedule.get("arrival_clock"):
        arrival_date = datetime.strptime(travel_date, "%Y-%m-%d")
        if schedule.get("arrival_next_day") or schedule["arrival_clock"] <= schedule.get("departure_clock", ""):
            arrival_date += timedelta(days=1)
        arrival_time = f"{arrival_date:%Y-%m-%d}T{schedule['arrival_clock']}:00"
    available = fare is not None
    return {
        "observation_id": f"obs_{uuid.uuid4().hex[:12]}",
        "collection_timestamp": datetime.now().astimezone().isoformat(),
        "route_id": route_id,
        "total_passengers": passengers,
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "advance_purchase_days": advance_days,
        "trip_type": "one_way",
        "passenger_count": 1,
        "cabin": "economy",
        "stops": schedule.get("stops"),
        "airline_code": "IX",
        "airline_name": "Air India Express",
        "flight_number": schedule.get("flight_number"),
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "duration_minutes": schedule.get("duration_minutes"),
        "fare_family": "Economy" if available else None,
        "base_fare": None,
        "taxes": None,
        "mandatory_fees": None,
        "total_fare": fare,
        "currency": "INR",
        "availability_status": "available" if available else ("collection_error" if error else "not_published"),
        "seats_available": None,
        "source": "Air India Express",
        "source_type": "airline_published_fare_page",
        "data_quality_score": 75 if available and schedule else (60 if available else 0),
        "no_flights": False if available else None,
        "sold_out": None,
        "source_url": source_url,
        "note": error,
    }


async def run_batch_scrape(headless=True):
    today = datetime.now()
    windows = [(days, (today + timedelta(days=days)).strftime("%Y-%m-%d")) for days in ADVANCE_WINDOWS]
    records = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})
        for index, (origin_city, destination_city, passengers) in enumerate(PRIORITY_ROUTES, 1):
            origin = CITY_TO_IATA[origin_city]
            destination = CITY_TO_IATA[destination_city]
            route_id = f"{origin_city}-{destination_city}"
            print(f"[{index}/{len(PRIORITY_ROUTES)}] {route_id}")
            target_dates = [date for _, date in windows]
            try:
                fares, schedules, source_url, error = await collect_route(
                    page, origin_city, destination_city, target_dates
                )
            except Exception as exc:
                fares, schedules, source_url, error = {}, [], route_url(origin_city, destination_city), str(exc)
            for advance_days, travel_date in windows:
                fare = fares.get(travel_date)
                if schedules and fare is not None:
                    for schedule in schedules:
                        records.append(normalized_record(
                            route_id, passengers, origin, destination, travel_date, advance_days,
                            source_url, fare, schedule, error,
                        ))
                else:
                    records.append(normalized_record(
                        route_id, passengers, origin, destination, travel_date, advance_days,
                        source_url, fare, None, error,
                    ))
            await asyncio.sleep(3)
        await browser.close()

    out_path = write_output(
        airline_slug="airindiaexpress",
        output_dir=OUTPUT_DIR,
        records=records,
        meta={
            "airline": "Air India Express",
            "base_url": BASE_URL,
            "robots_url": ROBOTS_URL,
            "robots_available": True,
            "crawl_allowed": True,
            "user_agent": USER_AGENT,
            "crawl_delay": None,
            "disallowed_paths": [],
            "sitemaps": [SITEMAP_URL],
            "advance_windows": ADVANCE_WINDOWS,
        },
    )
    print(f"Wrote {len(records)} records to {out_path}")
    return records


if __name__ == "__main__":
    asyncio.run(run_batch_scrape())