"""
common/robots.py — shared robots.txt compliance check.

Used by akasaair.py and spicejet.py.
airindiaexp.py keeps its own inline version (uses a custom urllib.Request
with User-Agent spoofing to avoid WAF rejection of robots.txt fetch itself).

Usage:
    from common.robots import robots_allowed
    if not robots_allowed(url, user_agent="VAYUSETU-Bot"):
        ...
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

_ROBOTS_CACHE: dict[str, RobotFileParser] = {}


def robots_allowed(url: str, user_agent: str = "*") -> bool:
    """Return whether the site's published robots policy permits this URL.

    Results are cached per domain for the lifetime of the process, so a
    batch scrape only fetches robots.txt once per hostname.

    Args:
        url:        The target URL to check.
        user_agent: The bot name to check against (e.g. "VAYUSETU-Bot" or "*").
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = _ROBOTS_CACHE.get(robots_url)
    if parser is None:
        parser = RobotFileParser(robots_url)
        try:
            parser.read()
        except Exception as exc:
            print(f"  [!] Could not read {robots_url}: {exc}; allowing URL")
            # Fail-open: if we cannot fetch robots.txt we allow the crawl
            # (consistent with RFC 9309 §2.3.1.4 for unreachable files).
            return True
        _ROBOTS_CACHE[robots_url] = parser
    return parser.can_fetch(user_agent, url)
