"""
orchestrator.py — Root-level orchestrator for VAYUSETU airline scrapers.

Runs each scraper as an isolated subprocess, captures stdout/stderr, and
computes data-quality metrics from their output JSON files.  On failure or
high null-rates, it calls the Groq-backed LLM triage layer (common.diagnose)
and takes automated action (retry, notify, flag for human review).

CLI flags:
    --only <airline>   Run only one scraper (akasaair | spicejet | airindiaexpress)
    --test             Dry run — skip subprocess execution, test metrics/diagnosis pipeline
    --verbose          Stream subprocess stdout live to console

Environment (loaded from .env if present):
    GROQ_API_KEY         — enables LLM failure diagnosis
    DISCORD_WEBHOOK_URL  — enables Discord alerting
"""

import argparse
import glob
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Environment loading — must happen before importing common.* that reads env
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional — env vars already set in shell

# Validate required env vars early, with clear guidance (not a crash)
_GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
_DISCORD_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
if not _GROQ_KEY:
    print(
        "[orchestrator] WARNING: GROQ_API_KEY not set — LLM diagnosis will be skipped.\n"
        "  Copy .env.example → .env and fill in your Groq key to enable diagnosis.",
        file=sys.stderr,
    )
if not _DISCORD_URL:
    print(
        "[orchestrator] WARNING: DISCORD_WEBHOOK_URL not set — Discord alerts disabled.\n"
        "  Copy .env.example → .env and fill in your webhook URL to enable alerts.",
        file=sys.stderr,
    )

from common.diagnose import diagnose_failure
from common.notify import send_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SCRAPERS: dict[str, str] = {
    "akasaair": "akasaair.py",
    "spicejet": "spicejet.py",
    "airindiaexpress": "airindiaexp.py",
}

# Null-rate threshold above which diagnosis is triggered even on "success"
NULL_RATE_ALERT_THRESHOLD = 0.30

# How long to wait before a diagnosis-driven retry (seconds)
RETRY_BACKOFF_DELAY = 60

# Track consecutive failures per scraper across the run (for repeat-alert logic)
_consecutive_failures: dict[str, int] = {name: 0 for name in SCRAPERS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_newest_output(airline_slug: str) -> Optional[Path]:
    """Find the most recently modified JSON output file for the given airline."""
    pattern = os.path.join(airline_slug, f"{airline_slug}_top_24_routes_*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    files.sort(key=os.path.getmtime)
    return Path(files[-1])


def compute_metrics(json_path: Path) -> dict:
    """Read an output file and compute missing-data metrics."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return {"error": f"Failed to read output: {exc}", "total_records": 0, "null_rate": 1.0}

    routes = data.get("routes", [])
    if not routes:
        return {"total_records": 0, "null_rate": 0.0}

    total_fields = 0
    null_fields = 0
    for record in routes:
        for val in record.values():
            total_fields += 1
            if val is None or val == "N/A" or val == 0:
                null_fields += 1

    return {
        "total_records": len(routes),
        "null_rate": round(null_fields / total_fields, 3) if total_fields else 0.0,
    }


def _handle_action(name: str, action: str, diagnosis: dict, stdout_buf: str) -> str:
    """Execute the orchestrator's response to a diagnosis suggested_action.

    Returns "retried" | "flagged" | "skipped" | "logged".
    """
    failure_class = diagnosis.get("failure_class", "unknown")
    explanation = diagnosis.get("explanation", "")

    if action == "retry_backoff":
        logger.info(
            "[%s] Diagnosis: %s (%s) → retry after %ds backoff",
            name, failure_class, explanation, RETRY_BACKOFF_DELAY,
        )
        return "retry_backoff_queued"

    elif action == "retry_new_proxy":
        logger.warning(
            "[%s] Diagnosis: %s → retry_new_proxy — no proxy infra configured, flagging.",
            name, failure_class,
        )
        send_alert(
            f"**{name}** needs a proxy rotation ({failure_class}):\n{explanation}",
            scraper_name=name,
            level="WARNING",
        )
        return "flagged_no_proxy"

    elif action in ("needs_selector_fix", "alert_human"):
        msg = (
            f"**{name}** requires human review.\n"
            f"Failure class: `{failure_class}`\n"
            f"Explanation: {explanation}\n"
            f"Action: `{action}`"
        )
        logger.error("[%s] %s — sending Discord alert", name, action)
        send_alert(msg, scraper_name=name, level="ERROR")
        return "human_review_required"

    elif action == "ignore_transient":
        logger.info(
            "[%s] Diagnosis: %s → transient, moving on", name, failure_class
        )
        return "ignored_transient"

    else:
        logger.warning("[%s] Unknown suggested_action: %s", name, action)
        return "logged"


def run_scraper(
    name: str,
    script_path: str,
    verbose: bool,
    dry_run: bool,
) -> dict:
    """Run one scraper script as a subprocess, diagnose on failure, return log entry."""
    result: dict = {
        "scraper": name,
        "start_time": datetime.now().isoformat(),
        "success": False,
        "duration_seconds": 0.0,
        "exit_code": None,
        "output_file": None,
        "metrics": {},
        "diagnosis": None,
        "orchestrator_action": None,
        "retried": False,
    }

    print(f"\n[{name}] Starting...")
    start_ts = time.time()
    stdout_buf = ""
    error_trace = ""

    if not dry_run:
        try:
            proc = subprocess.Popen(
                ["python", script_path],
                stdout=subprocess.PIPE if not verbose else None,
                stderr=subprocess.STDOUT if not verbose else None,
                text=True,
            )
            stdout_raw, _ = proc.communicate()
            stdout_buf = (stdout_raw or "")[-4000:]   # keep last 4000 chars
            result["exit_code"] = proc.returncode
            result["success"] = proc.returncode == 0
            if not result["success"]:
                error_trace = stdout_buf[-2000:]
        except Exception as exc:
            error_trace = str(exc)
            result["exit_code"] = -1
            result["success"] = False
    else:
        logger.info("[%s] DRY RUN — skipping subprocess execution", name)
        result["success"] = True
        result["exit_code"] = 0
        time.sleep(1)

    result["duration_seconds"] = round(time.time() - start_ts, 2)
    print(
        f"[{name}] Finished in {result['duration_seconds']}s  "
        f"(Exit {result['exit_code']})"
    )

    # Metrics
    out_path = find_newest_output(name)
    if out_path:
        result["output_file"] = str(out_path)
        metrics = compute_metrics(out_path)
        result["metrics"] = metrics
        null_rate = metrics.get("null_rate", 0.0)
        print(
            f"[{name}] Metrics: {metrics.get('total_records', 0)} records, "
            f"{null_rate*100:.1f}% null rate"
        )
    else:
        print(f"[{name}] No output file found.")
        result["metrics"] = {"total_records": 0, "null_rate": 1.0}
        null_rate = 1.0

    # Failure tracking
    if not result["success"]:
        _consecutive_failures[name] += 1
    else:
        _consecutive_failures[name] = 0

    # Diagnosis trigger: hard failure OR high null-rate
    needs_diagnosis = not result["success"] or null_rate > NULL_RATE_ALERT_THRESHOLD
    if needs_diagnosis and not dry_run:
        logger.info("[%s] Triggering LLM diagnosis (success=%s, null_rate=%.1f%%)",
                    name, result["success"], null_rate * 100)
        diagnosis = diagnose_failure(
            scraper_name=name,
            error_trace=error_trace,
            stdout_tail=stdout_buf[-2000:],
            dom_snapshot=None,   # no Playwright here; scrapers save their own screenshots
        )
        result["diagnosis"] = diagnosis
        action = diagnosis.get("suggested_action", "alert_human")

        # Check for consecutive failures BEFORE acting on action
        if _consecutive_failures.get(name, 0) >= 2:
            consec_msg = (
                f"**{name}** has failed {_consecutive_failures[name]} consecutive runs.\n"
                f"Last diagnosis: `{diagnosis.get('failure_class')}` — "
                f"{diagnosis.get('explanation', '')}"
            )
            send_alert(consec_msg, scraper_name=name, level="ERROR")

        orchestrator_action = _handle_action(name, action, diagnosis, stdout_buf)
        result["orchestrator_action"] = orchestrator_action

        # Retry once on backoff signal
        if orchestrator_action == "retry_backoff_queued" and not dry_run:
            print(f"[{name}] Waiting {RETRY_BACKOFF_DELAY}s before retry...")
            time.sleep(RETRY_BACKOFF_DELAY)
            retry_result = _run_subprocess(name, script_path, verbose)
            result["retried"] = True
            result["retry_exit_code"] = retry_result["exit_code"]
            result["retry_success"] = retry_result["success"]
            result["retry_duration_seconds"] = retry_result["duration_seconds"]
            if retry_result["success"]:
                _consecutive_failures[name] = 0
            print(
                f"[{name}] Retry {'succeeded' if retry_result['success'] else 'also failed'}"
            )
    elif needs_diagnosis and dry_run:
        # In dry-run mode, show a mock diagnosis to demonstrate the shape
        result["diagnosis"] = {
            "failure_class": "unknown",
            "explanation": "Dry run — no actual process to diagnose",
            "suggested_action": "ignore_transient",
            "confidence": 1.0,
            "diagnosis_source": "dry_run_mock",
        }
        result["orchestrator_action"] = "ignored_transient"

    return result


def _run_subprocess(name: str, script_path: str, verbose: bool) -> dict:
    """Helper: run a subprocess and return a minimal result dict."""
    start_ts = time.time()
    try:
        proc = subprocess.Popen(
            ["python", script_path],
            stdout=subprocess.PIPE if not verbose else None,
            stderr=subprocess.STDOUT if not verbose else None,
            text=True,
        )
        _, _ = proc.communicate()
        return {
            "exit_code": proc.returncode,
            "success": proc.returncode == 0,
            "duration_seconds": round(time.time() - start_ts, 2),
        }
    except Exception as exc:
        return {
            "exit_code": -1,
            "success": False,
            "duration_seconds": round(time.time() - start_ts, 2),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="VAYUSETU Scraper Orchestrator")
    parser.add_argument(
        "--only",
        choices=list(SCRAPERS.keys()),
        help="Run only this specific scraper",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Dry run: skip execution, test metrics/diagnosis pipeline on existing files",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Stream subprocess stdout live to console",
    )
    args = parser.parse_args()

    Path(".dist/logs").mkdir(parents=True, exist_ok=True)

    targets = {args.only: SCRAPERS[args.only]} if args.only else dict(SCRAPERS)
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    run_log: dict = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "dry_run": args.test,
        "scrapers": [],
    }

    for name, script_path in targets.items():
        res = run_scraper(name, script_path, args.verbose, args.test)
        run_log["scrapers"].append(res)

    log_path = Path(".dist") / "logs" / f"{run_id}.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2)

    print(f"\nRun complete. Log saved to {log_path}")

    fails = [s["scraper"] for s in run_log["scrapers"] if not s["success"]]
    if fails:
        print(f"FAILED: {', '.join(fails)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
