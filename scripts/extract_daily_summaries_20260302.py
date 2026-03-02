#!/usr/bin/env python3
"""
Extract daily summary metrics from raw API JSON and merge into a
long-term historical file (data/daily_summaries.json).

The historical file is append-only and git-committed so it persists
across CI runs.  It is keyed by date (YYYY-MM-DD) and stores one
compact record per day.  Duplicate dates are overwritten with the
latest data.

Usage:
    python extract_daily_summaries_20260302.py
    python extract_daily_summaries_20260302.py --input data/last_7_days.json
    python extract_daily_summaries_20260302.py --test  # dry-run, print to stdout
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

DEFAULT_INPUT = DATA_DIR / "last_7_days.json"
SUMMARIES_FILE = DATA_DIR / "daily_summaries.json"


def extract_day_summary(day_metrics: list) -> dict:
    """Compute a compact summary from one day's metric list."""
    hr_values = []
    sleep_rhr = None
    hrv = None
    recovery = None
    sleep_hours = None

    for metric in day_metrics:
        mtype = metric.get("type", "")
        obj = metric.get("object", {})

        if mtype == "hr":
            vals = obj.get("values", [])
            hr_values.extend(v["value"] for v in vals if "value" in v)

        elif mtype == "sleep_rhr":
            val = obj.get("value")
            if val is not None:
                sleep_rhr = val

        elif mtype == "night_rhr" and sleep_rhr is None:
            avg = obj.get("avg")
            if avg is not None:
                sleep_rhr = avg

        elif mtype == "hrv":
            val = obj.get("value") or obj.get("avg")
            if val is not None:
                hrv = val

        elif mtype == "recovery_score":
            val = obj.get("value") or obj.get("score")
            if val is not None:
                recovery = val

        elif mtype == "sleep":
            start = obj.get("bedtime_start")
            end = obj.get("bedtime_end")
            if start and end:
                sleep_hours = round((end - start) / 3600, 2)

    summary = {}
    if hr_values:
        summary["hr_avg"] = round(sum(hr_values) / len(hr_values), 1)
        summary["hr_min"] = min(hr_values)
        summary["hr_max"] = max(hr_values)
        summary["hr_readings"] = len(hr_values)
    if sleep_rhr is not None:
        summary["sleep_rhr"] = sleep_rhr
    if hrv is not None:
        summary["hrv"] = hrv
    if recovery is not None:
        summary["recovery"] = recovery
    if sleep_hours is not None:
        summary["sleep_hrs"] = sleep_hours

    return summary


def load_raw_metrics(json_path: Path) -> dict:
    """Load raw API JSON and return {date_str: [metric, ...]} dict."""
    with open(json_path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        metrics = {}
        for entry in data:
            day_metrics = (
                entry.get("data", {})
                .get("data", {})
                .get("metrics", {})
            )
            metrics.update(day_metrics)
    else:
        metrics = data.get("data", {}).get("metrics", {})

    return metrics


def load_existing_summaries() -> dict:
    """Load the existing historical summaries file, or return empty dict."""
    if SUMMARIES_FILE.exists():
        with open(SUMMARIES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_summaries(summaries: dict) -> None:
    """Write summaries back to disk, sorted by date."""
    DATA_DIR.mkdir(exist_ok=True)
    sorted_summaries = dict(sorted(summaries.items()))
    with open(SUMMARIES_FILE, "w") as f:
        json.dump(sorted_summaries, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Extract daily summaries and merge into historical file"
    )
    parser.add_argument(
        "--input", "-i",
        default=str(DEFAULT_INPUT),
        help="Raw API JSON file to extract from (default: data/last_7_days.json)",
    )
    parser.add_argument(
        "--test", "--dry-run",
        dest="test_mode",
        action="store_true",
        help="Print extracted summaries without writing to disk",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    raw_metrics = load_raw_metrics(input_path)
    if not raw_metrics:
        print("Warning: No metrics found in input file.", file=sys.stderr)
        sys.exit(0)

    new_summaries = {}
    for date_str, day_metrics in raw_metrics.items():
        summary = extract_day_summary(day_metrics)
        if summary:
            new_summaries[date_str] = summary

    print(f"Extracted summaries for {len(new_summaries)} day(s): "
          f"{min(new_summaries.keys())} to {max(new_summaries.keys())}")

    if args.test_mode:
        print("\n[DRY RUN] Would merge into historical file:")
        print(json.dumps(new_summaries, indent=2))
        return 0

    existing = load_existing_summaries()
    before_count = len(existing)

    existing.update(new_summaries)
    after_count = len(existing)

    save_summaries(existing)

    added = after_count - before_count
    updated = len(new_summaries) - added
    print(f"Historical file: {SUMMARIES_FILE}")
    print(f"  Total days: {after_count} ({added} new, {updated} updated)")
    date_range = sorted(existing.keys())
    print(f"  Date range: {date_range[0]} to {date_range[-1]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
