"""
common/notify.py — Discord webhook notification for critical scraper alerts.

Fires whenever a scraper diagnosis suggests "needs_selector_fix" or
"alert_human", or after 2+ consecutive failures for the same scraper.

The webhook URL is read from the environment variable DISCORD_WEBHOOK_URL.
If the variable is not set, the function logs a warning and returns silently
— it must never crash the orchestrator.

Usage:
    from common.notify import send_alert
    send_alert("SpiceJet scraper needs_selector_fix: #price element not found")
"""

import json
import logging
import os
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

# Max chars Discord embeds accept in description field
_DISCORD_MAX_DESC = 4000


def send_alert(message: str, scraper_name: str = "", level: str = "ERROR") -> bool:
    """Post an alert message to the configured Discord webhook.

    Args:
        message:       Human-readable alert text (≤ 4000 chars).
        scraper_name:  Optional scraper name used in the embed title.
        level:         "ERROR" (red), "WARNING" (yellow), or "INFO" (blue).

    Returns:
        True if the webhook call succeeded, False otherwise.
        Never raises — a notification failure should not stop the scraper run.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning(
            "DISCORD_WEBHOOK_URL not set — alert not sent: %s",
            message[:120],
        )
        return False

    colour_map = {"ERROR": 0xE74C3C, "WARNING": 0xF39C12, "INFO": 0x3498DB}
    colour = colour_map.get(level, 0xE74C3C)

    title = f"🚨 VAYUSETU Scraper Alert"
    if scraper_name:
        title += f" — {scraper_name}"

    payload = {
        "embeds": [
            {
                "title": title,
                "description": message[:_DISCORD_MAX_DESC],
                "color": colour,
                "footer": {"text": f"VAYUSETU • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            }
        ]
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
        if status in (200, 204):
            logger.info("Discord alert sent: %s", message[:60])
            return True
        logger.warning("Discord webhook returned HTTP %s", status)
        return False
    except Exception as exc:
        logger.error("Discord alert failed: %s", exc)
        return False
