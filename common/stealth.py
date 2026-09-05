"""
common/stealth.py — shared Playwright stealth helpers.

Both akasaair.py and spicejet.py apply playwright_stealth and launch with
--disable-blink-features=AutomationControlled.  airindiaexp.py does not use
stealth and should not import this module.

Usage:
    from common.stealth import apply_stealth, LAUNCH_ARGS
    browser = await p.chromium.launch(headless=headless, args=LAUNCH_ARGS)
    page = await browser.new_page(...)
    await apply_stealth(page)
"""

from playwright.async_api import Page

# Chromium launch args that suppress automation fingerprints.
LAUNCH_ARGS: list[str] = ["--disable-blink-features=AutomationControlled"]


async def apply_stealth(page: Page) -> None:
    """Apply playwright_stealth to the given page.

    Wraps playwright_stealth.Stealth().apply_stealth_async() so callers
    don't need to instantiate Stealth themselves.
    """
    try:
        from playwright_stealth import Stealth
        await Stealth().apply_stealth_async(page)
    except ImportError:
        # If playwright_stealth is not installed, skip silently.
        # The scraper will still function; stealth is best-effort.
        print("  [!] playwright_stealth not installed — running without stealth")
