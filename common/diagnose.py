"""
common/diagnose.py — LLM-based scraper failure triage via Groq API.

Classifies failures into structured categories so the orchestrator can
take appropriate automated action (retry, alert, ignore).  A Groq API
failure is caught and handled — it must never propagate to crash the
orchestrator.

Usage:
    from common.diagnose import diagnose_failure
    result = diagnose_failure(
        scraper_name="spicejet",
        error_trace="Traceback ...",
        stdout_tail="[!] no_api_captured ...",
        dom_snapshot="<html>Access Denied...</html>",
    )
    # result is always a DiagnosisResult dict, even if Groq fails
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema enforced on the LLM response
# ---------------------------------------------------------------------------

FAILURE_CLASSES = [
    "waf_block",
    "selector_broken",
    "rate_limited",
    "captcha",
    "network_error",
    "unknown",
]

SUGGESTED_ACTIONS = [
    "retry_backoff",
    "retry_new_proxy",
    "needs_selector_fix",
    "alert_human",
    "ignore_transient",
]

_SYSTEM_PROMPT = """\
You are an expert web-scraping reliability engineer.
You will be given information about a failed airline fare scraper run.
Your job is to classify the failure and suggest an automated action.

Return ONLY valid JSON matching EXACTLY this schema — no markdown, no code fences, no preamble:
{
  "failure_class": "<one of: waf_block | selector_broken | rate_limited | captcha | network_error | unknown>",
  "explanation": "<single sentence, ≤ 80 chars, plain English>",
  "suggested_action": "<one of: retry_backoff | retry_new_proxy | needs_selector_fix | alert_human | ignore_transient>",
  "confidence": <float 0.0-1.0>
}

Classification rules:
- waf_block: HTTP 403/406, Cloudflare challenge, "access denied", empty body from a known URL
- selector_broken: CSS/XPath element not found, locator timeout, changed DOM structure
- rate_limited: HTTP 429, exponential delays, "too many requests"
- captcha: CAPTCHA text visible in DOM, hCaptcha/reCAPTCHA challenge detected
- network_error: DNS failure, connection refused, SSL error, timeout on navigation
- unknown: insufficient evidence to classify — prefer this over a wrong classification

Action rules:
- retry_backoff: transient server issues, rate limiting, brief WAF kicks
- retry_new_proxy: persistent WAF/IP ban that a new IP would solve
- needs_selector_fix: DOM changed, selector stopped working — human must update code
- alert_human: CAPTCHA, persistent unknown failures, anomalies that need investigation
- ignore_transient: one-off network hiccup, partial data is acceptable
"""

_USER_PROMPT_TEMPLATE = """\
Scraper: {scraper_name}

Error trace (last 2000 chars):
{error_trace}

Stdout/stderr tail (last 2000 chars):
{stdout_tail}

DOM snapshot (truncated to 3000 chars, may be empty):
{dom_snapshot}

Classify this failure.
"""


# ---------------------------------------------------------------------------
# Public type alias (plain dict for simplicity / zero deps)
# ---------------------------------------------------------------------------

def _fallback_result(reason: str) -> dict:
    """Return a safe default when Groq is unavailable or returns garbage."""
    return {
        "failure_class": "unknown",
        "explanation": f"LLM diagnosis unavailable: {reason[:80]}",
        "suggested_action": "alert_human",
        "confidence": 0.0,
        "diagnosis_source": "fallback",
    }


def diagnose_failure(
    scraper_name: str,
    error_trace: str,
    stdout_tail: str,
    dom_snapshot: Optional[str] = None,
) -> dict:
    """Call Groq (llama-3.3-70b) to classify a scraper failure.

    Always returns a dict with keys:
        failure_class, explanation, suggested_action, confidence, diagnosis_source

    diagnosis_source is "groq" on success, "fallback" if anything goes wrong.

    Args:
        scraper_name:  Name of the scraper that failed (e.g. "spicejet").
        error_trace:   Python traceback or exception text.
        stdout_tail:   Last chunk of captured stdout/stderr.
        dom_snapshot:  Optional HTML content from a failure screenshot page.
    """
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("GROQ_API_KEY not set — skipping LLM diagnosis")
        return _fallback_result("GROQ_API_KEY not configured")

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        scraper_name=scraper_name,
        error_trace=(error_trace or "")[-2000:],
        stdout_tail=(stdout_tail or "")[-2000:],
        dom_snapshot=(dom_snapshot or "")[:3000],
    )

    try:
        from groq import Groq  # lazy import — keeps module importable without Groq installed
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,        # low randomness — we want deterministic classification
            max_tokens=256,
            timeout=20,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if the model misbehaves despite the prompt
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw)

        # Validate required fields and constrain to known values
        failure_class = parsed.get("failure_class", "unknown")
        if failure_class not in FAILURE_CLASSES:
            failure_class = "unknown"

        suggested_action = parsed.get("suggested_action", "alert_human")
        if suggested_action not in SUGGESTED_ACTIONS:
            suggested_action = "alert_human"

        return {
            "failure_class": failure_class,
            "explanation": str(parsed.get("explanation", ""))[:120],
            "suggested_action": suggested_action,
            "confidence": float(parsed.get("confidence", 0.5)),
            "diagnosis_source": "groq",
        }

    except json.JSONDecodeError as exc:
        logger.error("Groq returned non-JSON: %s", exc)
        return _fallback_result(f"JSON parse error: {exc}")
    except Exception as exc:
        logger.error("Groq diagnosis failed: %s", exc)
        return _fallback_result(str(exc))
