#!/usr/bin/env python3
"""
One-time backfill: import historical data from the Google Sheets CSV export
into data/daily_summaries.json.

Existing entries in daily_summaries.json (from the API) take priority over
CSV data.  CSV rows only fill in dates that are missing or add fields that
the existing entry lacks.

Usage:
    python backfill_from_csv_20260302.py
    python backfill_from_csv_20260302.py --input data/sleep_history.csv
    python backfill_from_csv_20260302.py --test
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

DEFAULT_CSV = DATA_DIR / "sleep_history.csv"
SUMMARIES_FILE = DATA_DIR / "daily_summaries.json"


def parse_csv_row(row: dict) -> tuple[str | None, dict]:
    """Parse one CSV row into (date_str, summary_dict). Returns (None, {}) on skip."""
    raw_date = row.get("Date", "").strip()
    if not raw_date:
        return None, {}

    try:
        dt = datetime.strptime(raw_date, "%m/%d/%y")
    except ValueError:
        try:
            dt = datetime.strptime(raw_date, "%m/%d/%Y")
        except ValueError:
            print(f"  Skipping unparseable date: {raw_date}", file=sys.stderr)
            return None, {}

    date_str = dt.strftime("%Y-%m-%d")
    summary = {}

    def safe_float(key):
        val = row.get(key, "").strip()
        if val:
            try:
                return float(val)
            except ValueError:
                pass
        return None

    def safe_int(key):
        val = row.get(key, "").strip()
        if val:
            try:
                return int(float(val))
            except ValueError:
                pass
        return None

    rhr = safe_float("Average RHR")
    if rhr is not None:
        summary["sleep_rhr"] = rhr

    hrv = safe_float("Average HRV")
    if hrv is not None:
        summary["hrv"] = hrv

    recovery = safe_int("Recovery Score")
    if recovery is not None:
        summary["recovery"] = recovery

    total_sleep_min = safe_float("Total Sleep")
    if total_sleep_min is not None:
        summary["sleep_hrs"] = round(total_sleep_min / 60, 2)

    return date_str, summary


def main():
    parser = argparse.ArgumentParser(description="Backfill daily summaries from CSV export")
    parser.add_argument("--input", "-i", default=str(DEFAULT_CSV),
                        help="CSV file to import")
    parser.add_argument("--test", "--dry-run", dest="test_mode", action="store_true",
                        help="Preview without writing")
    args = parser.parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Load existing summaries
    existing = {}
    if SUMMARIES_FILE.exists():
        with open(SUMMARIES_FILE, "r") as f:
            existing = json.load(f)

    # Parse CSV
    imported = {}
    skipped = 0
    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str, summary = parse_csv_row(row)
            if date_str is None or not summary:
                skipped += 1
                continue
            imported[date_str] = summary

    print(f"CSV: {len(imported)} days parsed, {skipped} rows skipped")
    if imported:
        csv_dates = sorted(imported.keys())
        print(f"  Range: {csv_dates[0]} to {csv_dates[-1]}")

    # Merge: CSV fills gaps, existing API data takes priority
    merged = dict(existing)
    new_dates = 0
    enriched_dates = 0

    for date_str, csv_summary in imported.items():
        if date_str not in merged:
            merged[date_str] = csv_summary
            new_dates += 1
        else:
            before = set(merged[date_str].keys())
            for key, val in csv_summary.items():
                if key not in merged[date_str]:
                    merged[date_str][key] = val
            after = set(merged[date_str].keys())
            if after - before:
                enriched_dates += 1

    print(f"\nMerge result:")
    print(f"  {new_dates} new dates added from CSV")
    print(f"  {enriched_dates} existing dates enriched with CSV fields")
    print(f"  Total days: {len(merged)}")

    if args.test_mode:
        print("\n[DRY RUN] Sample of imported data:")
        for d in sorted(imported.keys())[:5]:
            print(f"  {d}: {imported[d]}")
        return 0

    sorted_merged = dict(sorted(merged.items()))
    DATA_DIR.mkdir(exist_ok=True)
    with open(SUMMARIES_FILE, "w") as f:
        json.dump(sorted_merged, f, indent=2)
        f.write("\n")

    all_dates = sorted(sorted_merged.keys())
    print(f"\nWritten to {SUMMARIES_FILE}")
    print(f"  Full range: {all_dates[0]} to {all_dates[-1]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
