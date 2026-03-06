#!/usr/bin/env python3
"""
Ultrahuman API Query Script
Queries personal health metrics from the Ultrahuman Vision API.

Usage:
    python ultrahuman_query_20251209.py --date 2025-12-09
    python ultrahuman_query_20251209.py --start-date 2025-12-01 --end-date 2025-12-09
    python ultrahuman_query_20251209.py --test  # Dry run mode

Environment Variables Required:
    ULTRAHUMAN_API_TOKEN - Your Ultrahuman API access token
    ULTRAHUMAN_EMAIL - Your Ultrahuman account email
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Optional: load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, use environment variables directly

# API Configuration
BASE_URL = "https://partner.ultrahuman.com"
METRICS_ENDPOINT = "/api/v1/partner/daily_metrics"

# State file for continuation
STATE_FILE = Path(__file__).parent / ".ultrahuman_state.json"


def load_state():
    """Load the last queried date from state file."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    """Save current state to file for continuation."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_credentials():
    """Load API credentials from environment variables."""
    token = os.environ.get("ULTRAHUMAN_API_TOKEN")
    
    if not token:
        print("Error: ULTRAHUMAN_API_TOKEN environment variable not set.")
        print("Set it with: export ULTRAHUMAN_API_TOKEN='your_token_here'")
        sys.exit(1)
    
    return token


def fetch_metrics(token, date_str, test_mode=False):
    """
    Fetch metrics for a specific date.
    
    Args:
        token: API access token
        date_str: Date in YYYY-MM-DD format
        test_mode: If True, only print the request without executing
    
    Returns:
        dict: API response data or None on error
    """
    url = f"{BASE_URL}{METRICS_ENDPOINT}"
    headers = {
        "Authorization": token,  # No "Bearer" prefix per Ultrahuman docs
        "Content-Type": "application/json"
    }
    params = {
        "date": date_str
    }
    
    if test_mode:
        print(f"\n[DRY RUN] Would request:")
        print(f"  URL: {url}")
        print(f"  Headers: Authorization: {'*' * 20}...")
        print(f"  Params: date={date_str}")
        return {"test_mode": True, "date": date_str}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error for {date_str}: {e}")
        if response.status_code == 401:
            print("  -> Token may be expired. Please refresh your access token.")
        elif response.status_code == 403:
            print("  -> Access denied. Check your API permissions.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Request Error for {date_str}: {e}")
        return None


def date_range(start_date, end_date):
    """Generate dates between start and end (inclusive)."""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(
        description="Query Ultrahuman metrics data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--date", "-d",
        help="Single date to query (YYYY-MM-DD). Defaults to today."
    )
    parser.add_argument(
        "--start-date", "-s",
        help="Start date for range query (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date", "-e",
        help="End date for range query (YYYY-MM-DD). Defaults to today."
    )
    parser.add_argument(
        "--continue", "-c",
        dest="continue_from_last",
        action="store_true",
        help="Continue from the last successfully queried date"
    )
    parser.add_argument(
        "--test", "--dry-run",
        dest="test_mode",
        action="store_true",
        help="Dry run mode - show what would be requested without making API calls"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (JSON). Defaults to stdout."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of days to query (default: 10)"
    )
    parser.add_argument(
        "--weeks-back",
        dest="weeks_back",
        type=int,
        default=None,
        metavar="N",
        help="Fetch N weeks of history ending today (e.g. --weeks-back 4 fetches 28 days). "
             "Overrides --date, --start-date, and --end-date."
    )
    
    args = parser.parse_args()
    
    # Get credentials
    if args.test_mode:
        token = os.environ.get("ULTRAHUMAN_API_TOKEN", "TEST_TOKEN_PLACEHOLDER")
        print("[DRY RUN MODE ENABLED]")
    else:
        token = get_credentials()
    
    # Determine date range
    today = datetime.now().date()

    if args.weeks_back is not None:
        start_date = today - timedelta(days=args.weeks_back * 7 - 1)
        end_date = today
        # Override the default limit so it covers the full requested window
        if args.limit < args.weeks_back * 7:
            args.limit = args.weeks_back * 7
        print(f"Fetching {args.weeks_back} week(s) of history: {start_date} to {end_date}")
    elif args.continue_from_last:
        state = load_state()
        last_date = state.get("last_queried_date")
        if last_date:
            start_date = datetime.strptime(last_date, "%Y-%m-%d").date() + timedelta(days=1)
            print(f"Continuing from {start_date} (after last queried: {last_date})")
        else:
            start_date = today - timedelta(days=7)
            print(f"No previous state found. Starting from {start_date}")
        end_date = today
    elif args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date() if args.end_date else today
    elif args.date:
        start_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        end_date = start_date
    else:
        start_date = today
        end_date = today
    
    # Query metrics
    results = []
    dates_queried = 0
    last_successful_date = None
    
    print(f"\nQuerying metrics from {start_date} to {end_date}")
    print("-" * 50)
    
    for query_date in date_range(start_date, end_date):
        if dates_queried >= args.limit:
            print(f"\nReached limit of {args.limit} days. Use --continue to resume later.")
            break
        
        date_str = query_date.strftime("%Y-%m-%d")
        print(f"Fetching {date_str}...", end=" ")
        
        data = fetch_metrics(token, date_str, test_mode=args.test_mode)
        
        if data:
            results.append({"date": date_str, "data": data})
            last_successful_date = date_str
            if not args.test_mode:
                print("OK")
            dates_queried += 1
        else:
            print("FAILED")
    
    # Save state for continuation
    if last_successful_date and not args.test_mode:
        save_state({"last_queried_date": last_successful_date})
        print(f"\nState saved. Last successful date: {last_successful_date}")
    
    # Output results
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_path}")
    else:
        print("\n" + "=" * 50)
        print("RESULTS:")
        print("=" * 50)
        print(json.dumps(results, indent=2))
    
    print(f"\nTotal days queried: {len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

