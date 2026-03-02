#!/usr/bin/env python3
"""
Build a self-contained HTML dashboard from Ultrahuman chart images and JSON data.

Embeds chart PNGs as base64 so the page works with no external dependencies.
Designed for GitHub Pages deployment via Actions.

Usage:
    python build_page_20260302.py
    python build_page_20260302.py --test  # Write to stdout instead of file
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "output"
SITE_DIR = PROJECT_DIR / "_site"

LOCAL_TZ = ZoneInfo("America/Los_Angeles")


def encode_image(path: Path) -> str:
    """Base64-encode a PNG file for embedding in HTML."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def extract_summary(json_path: Path) -> dict:
    """Pull headline stats from the raw metrics JSON."""
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

    dates = sorted(metrics.keys())
    days_count = len(dates)

    hr_values = []
    sleep_rhr_values = []
    hrv_values = []
    recovery_scores = []
    sleep_durations = []

    for date_str, day_metrics in metrics.items():
        for metric in day_metrics:
            mtype = metric.get("type", "")
            obj = metric.get("object", {})

            if mtype == "hr":
                vals = obj.get("values", [])
                hr_values.extend(v["value"] for v in vals if "value" in v)

            elif mtype == "sleep_rhr":
                val = obj.get("value")
                if val is not None:
                    sleep_rhr_values.append(val)

            elif mtype == "night_rhr" and not sleep_rhr_values:
                avg = obj.get("avg")
                if avg is not None:
                    sleep_rhr_values.append(avg)

            elif mtype == "hrv":
                val = obj.get("value") or obj.get("avg")
                if val is not None:
                    hrv_values.append(val)

            elif mtype == "recovery_score":
                val = obj.get("value") or obj.get("score")
                if val is not None:
                    recovery_scores.append(val)

            elif mtype == "sleep":
                start = obj.get("bedtime_start")
                end = obj.get("bedtime_end")
                if start and end:
                    sleep_durations.append((end - start) / 3600)

    summary = {
        "date_range": f"{dates[0]} to {dates[-1]}" if dates else "N/A",
        "days": days_count,
        "hr_readings": len(hr_values),
    }

    if hr_values:
        summary["hr_avg"] = f"{sum(hr_values) / len(hr_values):.0f}"
        summary["hr_min"] = str(min(hr_values))
        summary["hr_max"] = str(max(hr_values))
    if sleep_rhr_values:
        summary["sleep_rhr_avg"] = f"{sum(sleep_rhr_values) / len(sleep_rhr_values):.0f}"
    if hrv_values:
        summary["hrv_avg"] = f"{sum(hrv_values) / len(hrv_values):.0f}"
    if recovery_scores:
        summary["recovery_avg"] = f"{sum(recovery_scores) / len(recovery_scores):.0f}"
    if sleep_durations:
        summary["sleep_avg_hrs"] = f"{sum(sleep_durations) / len(sleep_durations):.1f}"

    return summary


def build_stat_card(label: str, value: str, unit: str = "") -> str:
    """Return HTML for a single metric card."""
    return f"""<div class="stat-card">
  <div class="stat-value">{value}<span class="stat-unit">{unit}</span></div>
  <div class="stat-label">{label}</div>
</div>"""


def build_html(summary: dict, dense_b64: str | None, weekly_b64: str | None, updated: str) -> str:
    """Assemble the full HTML page."""

    cards = []
    if "hr_avg" in summary:
        cards.append(build_stat_card("Avg Heart Rate", summary["hr_avg"], " bpm"))
    if "sleep_rhr_avg" in summary:
        cards.append(build_stat_card("Sleep Resting HR", summary["sleep_rhr_avg"], " bpm"))
    if "hrv_avg" in summary:
        cards.append(build_stat_card("Avg HRV", summary["hrv_avg"], " ms"))
    if "recovery_avg" in summary:
        cards.append(build_stat_card("Recovery Score", summary["recovery_avg"]))
    if "sleep_avg_hrs" in summary:
        cards.append(build_stat_card("Avg Sleep", summary["sleep_avg_hrs"], " hrs"))
    cards.append(build_stat_card("Days Tracked", str(summary.get("days", 0))))

    cards_html = "\n".join(cards)

    dense_img = (
        f'<img src="data:image/png;base64,{dense_b64}" alt="Heart rate last 100 readings">'
        if dense_b64
        else '<p class="no-data">Dense chart not available</p>'
    )
    weekly_img = (
        f'<img src="data:image/png;base64,{weekly_b64}" alt="Heart rate 7-day overview">'
        if weekly_b64
        else '<p class="no-data">Weekly chart not available</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ultrahuman Dashboard</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
    padding: 2rem 1rem;
  }}

  .container {{
    max-width: 960px;
    margin: 0 auto;
  }}

  header {{
    text-align: center;
    margin-bottom: 2rem;
  }}
  header h1 {{
    font-size: 1.8rem;
    color: #f0f6fc;
    font-weight: 700;
    letter-spacing: -0.02em;
  }}
  header .subtitle {{
    color: #8b949e;
    font-size: 0.95rem;
    margin-top: 0.3rem;
  }}

  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
  }}
  .stat-card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1.2rem 1rem;
    text-align: center;
  }}
  .stat-value {{
    font-size: 1.6rem;
    font-weight: 700;
    color: #f0f6fc;
  }}
  .stat-unit {{
    font-size: 0.85rem;
    font-weight: 400;
    color: #8b949e;
  }}
  .stat-label {{
    font-size: 0.8rem;
    color: #8b949e;
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}

  .chart-section {{
    margin-bottom: 2rem;
  }}
  .chart-section h2 {{
    font-size: 1.1rem;
    color: #f0f6fc;
    margin-bottom: 0.8rem;
    font-weight: 600;
  }}
  .chart-section img {{
    width: 100%;
    border-radius: 10px;
    border: 1px solid #30363d;
  }}
  .no-data {{
    color: #8b949e;
    font-style: italic;
    padding: 2rem;
    text-align: center;
    background: #161b22;
    border-radius: 10px;
    border: 1px solid #30363d;
  }}

  footer {{
    text-align: center;
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid #21262d;
    color: #484f58;
    font-size: 0.8rem;
  }}
  footer a {{
    color: #58a6ff;
    text-decoration: none;
  }}
  footer a:hover {{
    text-decoration: underline;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Ultrahuman Dashboard</h1>
    <div class="subtitle">{summary.get("date_range", "")}</div>
  </header>

  <div class="stats-grid">
    {cards_html}
  </div>

  <div class="chart-section">
    <h2>Recent Heart Rate (Last 100 Readings)</h2>
    {dense_img}
  </div>

  <div class="chart-section">
    <h2>7-Day Heart Rate Overview</h2>
    {weekly_img}
  </div>

  <footer>
    Updated {updated} &middot;
    Data from <a href="https://vision.ultrahuman.com" target="_blank">Ultrahuman Vision</a>
  </footer>
</div>
</body>
</html>
"""


def find_latest_chart(prefix: str) -> Path | None:
    """Find the most recently dated chart file matching a prefix."""
    candidates = sorted(OUTPUT_DIR.glob(f"{prefix}_*.png"))
    return candidates[-1] if candidates else None


def main():
    parser = argparse.ArgumentParser(description="Build Ultrahuman dashboard HTML page")
    parser.add_argument("--test", "--dry-run", dest="test_mode", action="store_true",
                        help="Print HTML to stdout instead of writing to _site/")
    parser.add_argument("--data", default=str(DATA_DIR / "last_7_days.json"),
                        help="Input JSON data file")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    summary = extract_summary(data_path)

    dense_path = find_latest_chart("hr_dense")
    weekly_path = find_latest_chart("hr_weekly")

    dense_b64 = encode_image(dense_path) if dense_path else None
    weekly_b64 = encode_image(weekly_path) if weekly_path else None

    if not dense_b64 and not weekly_b64:
        print("Warning: No chart images found in output/. Run hr_charts first.", file=sys.stderr)

    now = datetime.now(LOCAL_TZ)
    updated = now.strftime("%B %-d, %Y at %-I:%M %p %Z")

    html = build_html(summary, dense_b64, weekly_b64, updated)

    if args.test_mode:
        print(html)
    else:
        SITE_DIR.mkdir(exist_ok=True)
        out_path = SITE_DIR / "index.html"
        with open(out_path, "w") as f:
            f.write(html)
        print(f"Dashboard written to {out_path}")
        print(f"  Data range: {summary.get('date_range', 'N/A')}")
        print(f"  HR readings: {summary.get('hr_readings', 0)}")
        print(f"  Dense chart: {dense_path or 'missing'}")
        print(f"  Weekly chart: {weekly_path or 'missing'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
