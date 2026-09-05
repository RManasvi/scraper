import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

FSA_URL_TEMPLATE = (
    "https://www.airindiaexpress.com/flight-availability?"
    "/{origin}/{destination}/{date}/N/1/0/0/0/0/0/0/O/FLAT10/INR/ST"
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


async def debug_network(origin, destination, start_date):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(user_agent=USER_AGENT, viewport={"width": 1366, "height": 768})

        def log_request(request):
            if request.method == "POST" or "lowFares" in request.url or "flight-availability" in request.url:
                print(f"[REQUEST] {request.method} {request.url}")

        def log_response(response):
            if "lowFares" in response.url:
                print(f"[RESPONSE] {response.status} {response.url}")

        page.on("request", log_request)
        page.on("response", log_response)

        url = FSA_URL_TEMPLATE.format(origin=origin, destination=destination, date=start_date)
        print(f"[NAV] Going to {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        print("[WAIT] Watching network for 20 seconds...")
        await page.wait_for_timeout(20000)

        await browser.close()
        print("[DONE]")


if __name__ == "__main__":
    asyncio.run(debug_network("DEL", "BOM", datetime.now().strftime("%Y-%m-%d")))