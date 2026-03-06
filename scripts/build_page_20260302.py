#!/usr/bin/env python3
"""
Build self-contained HTML dashboards from Ultrahuman data.

Produces two pages:
  _site/index.html   -- 7-day view with embedded chart PNGs (existing)
  _site/monthly.html  -- month-selectable view using Chart.js + inline JSON

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
SUMMARIES_FILE = DATA_DIR / "daily_summaries.json"

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


NAV_CSS = """
  nav {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
  }
  nav a {
    color: #8b949e;
    text-decoration: none;
    padding: 0.4rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    border: 1px solid #30363d;
    transition: all 0.15s;
  }
  nav a:hover { color: #f0f6fc; border-color: #58a6ff; }
  nav a.active { color: #f0f6fc; background: #161b22; border-color: #58a6ff; }
"""

SHARED_CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    min-height: 100vh;
    padding: 2rem 1rem;
  }

  .container {
    max-width: 960px;
    margin: 0 auto;
  }

  header {
    text-align: center;
    margin-bottom: 0.8rem;
  }
  header h1 {
    font-size: 1.8rem;
    color: #f0f6fc;
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  header .subtitle {
    color: #8b949e;
    font-size: 0.95rem;
    margin-top: 0.3rem;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 1rem;
    margin-bottom: 2.5rem;
  }
  .stat-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1.2rem 1rem;
    text-align: center;
  }
  .stat-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: #f0f6fc;
  }
  .stat-unit {
    font-size: 0.85rem;
    font-weight: 400;
    color: #8b949e;
  }
  .stat-label {
    font-size: 0.8rem;
    color: #8b949e;
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .chart-section {
    margin-bottom: 2rem;
  }
  .chart-section h2 {
    font-size: 1.1rem;
    color: #f0f6fc;
    margin-bottom: 0.8rem;
    font-weight: 600;
  }
  .chart-section img {
    width: 100%;
    border-radius: 10px;
    border: 1px solid #30363d;
  }
  .no-data {
    color: #8b949e;
    font-style: italic;
    padding: 2rem;
    text-align: center;
    background: #161b22;
    border-radius: 10px;
    border: 1px solid #30363d;
  }

  footer {
    text-align: center;
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid #21262d;
    color: #484f58;
    font-size: 0.8rem;
  }
  footer a {
    color: #58a6ff;
    text-decoration: none;
  }
  footer a:hover {
    text-decoration: underline;
  }
"""


def build_nav(active: str) -> str:
    """Return nav HTML with the active page highlighted."""
    links = [
        ("index.html", "Weekly"),
        ("monthly.html", "Monthly"),
    ]
    parts = []
    for href, label in links:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    return f'<nav>{"".join(parts)}</nav>'


def build_html(
    summary: dict,
    dense_b64: str | None,
    weekly_charts: list[tuple[str, str]],
    updated: str,
) -> str:
    """Assemble the weekly (index) HTML page.

    Args:
        weekly_charts: List of (label, base64_png) tuples ordered current → oldest.
    """

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

    # Build week-navigation panel
    if weekly_charts:
        tab_buttons = "\n".join(
            f'  <button class="week-tab{" active" if i == 0 else ""}" '
            f'onclick="showWeek({i})">{label}</button>'
            for i, (label, _) in enumerate(weekly_charts)
        )
        tab_panels = "\n".join(
            f'  <div class="week-panel{" active" if i == 0 else ""}" id="week-{i}">'
            f'<img src="data:image/png;base64,{b64}" alt="Heart rate {lbl}"></div>'
            for i, (lbl, b64) in enumerate(weekly_charts)
        )
        weekly_section = f"""
  <div class="week-tabs">{tab_buttons}</div>
  <div class="week-panels">
{tab_panels}
  </div>
  <script>
    function showWeek(idx) {{
      document.querySelectorAll('.week-tab').forEach((b, i) => b.classList.toggle('active', i === idx));
      document.querySelectorAll('.week-panel').forEach((p, i) => p.classList.toggle('active', i === idx));
    }}
  </script>"""
    else:
        weekly_section = '<p class="no-data">Weekly chart not available</p>'

    nav = build_nav("index.html")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ultrahuman Dashboard</title>
<style>
{SHARED_CSS}
{NAV_CSS}
  .week-tabs {{
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
  }}
  .week-tab {{
    background: #161b22;
    border: 1px solid #30363d;
    color: #8b949e;
    padding: 0.35rem 0.9rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    transition: all 0.15s;
  }}
  .week-tab:hover {{ border-color: #58a6ff; color: #f0f6fc; }}
  .week-tab.active {{ border-color: #58a6ff; color: #f0f6fc; background: #1f3a5c; }}
  .week-panel {{ display: none; }}
  .week-panel.active {{ display: block; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Ultrahuman Dashboard</h1>
    <div class="subtitle">{summary.get("date_range", "")}</div>
  </header>

  {nav}

  <div class="stats-grid">
    {cards_html}
  </div>

  <div class="chart-section">
    <h2>Recent Heart Rate (Last 100 Readings)</h2>
    {dense_img}
  </div>

  <div class="chart-section">
    <h2>7-Day Heart Rate Overview</h2>
    {weekly_section}
  </div>

  <footer>
    Updated {updated} &middot;
    Data from <a href="https://vision.ultrahuman.com" target="_blank">Ultrahuman Vision</a>
  </footer>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Monthly page
# ---------------------------------------------------------------------------

def load_daily_summaries() -> dict:
    """Load the historical daily_summaries.json, or return empty dict."""
    if SUMMARIES_FILE.exists():
        with open(SUMMARIES_FILE, "r") as f:
            return json.load(f)
    return {}


def build_monthly_html(summaries_json: str, updated: str) -> str:
    """Assemble the monthly HTML page with inline Chart.js."""

    nav = build_nav("monthly.html")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ultrahuman - Monthly View</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
{SHARED_CSS}
{NAV_CSS}

  .month-picker {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .month-picker button {{
    background: #161b22;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.15s;
  }}
  .month-picker button:hover {{ border-color: #58a6ff; color: #f0f6fc; }}
  .month-picker button:disabled {{ opacity: 0.3; cursor: default; border-color: #30363d; }}
  .month-picker span {{
    font-size: 1.1rem;
    font-weight: 600;
    color: #f0f6fc;
    min-width: 160px;
    text-align: center;
  }}

  .chart-box {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1.2rem;
    margin-bottom: 2rem;
  }}
  .chart-box h2 {{
    font-size: 1rem;
    color: #f0f6fc;
    margin-bottom: 0.8rem;
    font-weight: 600;
  }}
  .chart-box canvas {{
    width: 100% !important;
  }}

  .section-heading {{
    font-size: 0.75rem;
    color: #58a6ff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    margin: 2rem 0 0.8rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #21262d;
  }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Ultrahuman Dashboard</h1>
    <div class="subtitle">Monthly Activity</div>
  </header>

  {nav}

  <div class="month-picker">
    <button id="prevMonth">&larr;</button>
    <span id="monthLabel"></span>
    <button id="nextMonth">&rarr;</button>
  </div>

  <div class="stats-grid" id="statsGrid"></div>

  <div class="section-heading">Sleep</div>

  <div class="chart-box">
    <h2>Sleep Score</h2>
    <canvas id="sleepScoreChart" height="160"></canvas>
  </div>

  <div class="chart-box">
    <h2>Sleep Duration &amp; Time in Bed</h2>
    <canvas id="sleepChart" height="180"></canvas>
  </div>

  <div class="chart-box">
    <h2>Sleep Stages</h2>
    <canvas id="sleepStagesChart" height="200"></canvas>
  </div>

  <div class="chart-box">
    <h2>Sleep Efficiency</h2>
    <canvas id="efficiencyChart" height="160"></canvas>
  </div>

  <div class="section-heading">Heart Rate &amp; HRV</div>

  <div class="chart-box">
    <h2>Heart Rate</h2>
    <canvas id="hrChart" height="200"></canvas>
  </div>

  <div class="chart-box">
    <h2>HRV</h2>
    <canvas id="hrvChart" height="160"></canvas>
  </div>

  <div class="section-heading">Recovery &amp; Activity</div>

  <div class="chart-box">
    <h2>Recovery Score</h2>
    <canvas id="recoveryChart" height="160"></canvas>
  </div>

  <div class="chart-box">
    <h2>SpO2</h2>
    <canvas id="spo2Chart" height="140"></canvas>
  </div>

  <footer>
    Updated {updated} &middot;
    Data from <a href="https://vision.ultrahuman.com" target="_blank">Ultrahuman Vision</a>
  </footer>
</div>

<script>
const ALL_DATA = {summaries_json};

const MONTHS = Object.keys(ALL_DATA)
  .map(d => d.slice(0, 7))
  .filter((v, i, a) => a.indexOf(v) === i)
  .sort();

let currentIdx = MONTHS.length - 1;

const chartDefaults = {{
  responsive: true,
  animation: false,
  plugins: {{
    legend: {{ display: false }},
    tooltip: {{
      backgroundColor: '#161b22',
      borderColor: '#30363d',
      borderWidth: 1,
      titleColor: '#f0f6fc',
      bodyColor: '#c9d1d9',
    }}
  }},
  scales: {{
    x: {{
      ticks: {{ color: '#8b949e', maxRotation: 0 }},
      grid: {{ color: 'rgba(255,255,255,0.06)' }}
    }},
    y: {{
      ticks: {{ color: '#8b949e' }},
      grid: {{ color: 'rgba(255,255,255,0.06)' }}
    }}
  }}
}};

function makeChart(canvasId, label, color, fillColor) {{
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {{
    type: 'line',
    data: {{ labels: [], datasets: [{{
      label: label, data: [],
      borderColor: color,
      backgroundColor: fillColor || 'transparent',
      fill: !!fillColor, tension: 0.3,
      pointRadius: 3, pointBackgroundColor: color, borderWidth: 2,
    }}] }},
    options: structuredClone(chartDefaults)
  }});
}}

function makeBarChart(canvasId) {{
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {{
    type: 'bar',
    data: {{ labels: [], datasets: [] }},
    options: structuredClone(chartDefaults)
  }});
}}

// Sleep charts
const sleepScoreChart = makeChart('sleepScoreChart', 'Sleep Score', '#58a6ff', 'rgba(88,166,255,0.15)');
const sleepChart = makeChart('sleepChart', 'Sleep', '#9b59b6', 'rgba(155,89,182,0.15)');
const sleepStagesChart = makeBarChart('sleepStagesChart');
const efficiencyChart = makeChart('efficiencyChart', 'Efficiency', '#4ecdc4', 'rgba(78,205,196,0.15)');

// HR charts
const hrChart = makeChart('hrChart', 'Avg HR', '#ff6b6b', 'rgba(255,107,107,0.15)');
const hrvChart = makeChart('hrvChart', 'HRV', '#4ecdc4', 'rgba(78,205,196,0.15)');

// Recovery & activity
const recoveryChart = makeChart('recoveryChart', 'Recovery', '#87bc40', 'rgba(135,188,64,0.15)');
const spo2Chart = makeChart('spo2Chart', 'SpO2', '#f09d4f', 'rgba(240,157,79,0.15)');

function makeStatCard(label, value, unit) {{
  return '<div class="stat-card">'
    + '<div class="stat-value">' + value + '<span class="stat-unit">' + (unit || '') + '</span></div>'
    + '<div class="stat-label">' + label + '</div></div>';
}}

const avg = (arr) => {{
  const valid = arr.filter(v => v !== null && v !== undefined);
  return valid.length ? (valid.reduce((a, b) => a + b, 0) / valid.length) : null;
}};

function updateView() {{
  const month = MONTHS[currentIdx];
  const [y, m] = month.split('-');
  const monthName = new Date(parseInt(y), parseInt(m) - 1, 1)
    .toLocaleString('en-US', {{ month: 'long', year: 'numeric' }});
  document.getElementById('monthLabel').textContent = monthName;
  document.getElementById('prevMonth').disabled = (currentIdx === 0);
  document.getElementById('nextMonth').disabled = (currentIdx === MONTHS.length - 1);

  const days = Object.keys(ALL_DATA).filter(d => d.startsWith(month)).sort();
  const labels = days.map(d => parseInt(d.split('-')[2]));
  const get = (field) => days.map(d => ALL_DATA[d][field] ?? null);

  // Data arrays
  const hrAvg = get('hr_avg');
  const hrMin = get('hr_min');
  const hrMax = get('hr_max');
  const sleepRhr = get('sleep_rhr');
  const hrv = get('hrv');
  const sleepHrv = get('sleep_hrv');
  const recovery = get('recovery');
  const sleepHrs = get('sleep_hrs');
  const sleepScore = get('sleep_score');
  const deepMin = get('deep_sleep_min');
  const remMin = get('rem_sleep_min');
  const lightMin = get('light_sleep_min');
  const sleepEff = get('sleep_efficiency');
  const tibMin = get('time_in_bed_min');
  const spo2 = get('spo2');

  // --- Stats cards ---
  const grid = document.getElementById('statsGrid');
  let cards = '';
  const aScore = avg(sleepScore);
  if (aScore !== null) cards += makeStatCard('Sleep Score', aScore.toFixed(0), '');
  const aSleep = avg(sleepHrs);
  if (aSleep !== null) cards += makeStatCard('Avg Sleep', aSleep.toFixed(1), ' hrs');
  const aEff = avg(sleepEff);
  if (aEff !== null) cards += makeStatCard('Sleep Efficiency', aEff.toFixed(0), '%');
  const aRhr = avg(sleepRhr);
  if (aRhr !== null) cards += makeStatCard('Sleep RHR', aRhr.toFixed(0), ' bpm');
  const aHrv = avg(hrv);
  if (aHrv !== null) cards += makeStatCard('Avg HRV', aHrv.toFixed(0), ' ms');
  const aRec = avg(recovery);
  if (aRec !== null) cards += makeStatCard('Recovery', aRec.toFixed(0), '');
  cards += makeStatCard('Days Tracked', String(days.length), '');
  grid.innerHTML = cards;

  // --- Sleep Score chart ---
  sleepScoreChart.data.labels = labels;
  sleepScoreChart.data.datasets[0].data = sleepScore;
  sleepScoreChart.options.scales.y.min = 0;
  sleepScoreChart.options.scales.y.max = 100;
  sleepScoreChart.update();

  // --- Sleep Duration chart ---
  const tibHrs = tibMin.map(v => v !== null ? +(v / 60).toFixed(2) : null);
  sleepChart.data.labels = labels;
  sleepChart.data.datasets = [
    {{
      label: 'Total Sleep',
      data: sleepHrs,
      borderColor: '#9b59b6',
      backgroundColor: 'rgba(155,89,182,0.15)',
      fill: true, tension: 0.3,
      pointRadius: 3, pointBackgroundColor: '#9b59b6', borderWidth: 2,
    }},
    {{
      label: 'Time in Bed',
      data: tibHrs,
      borderColor: 'rgba(155,89,182,0.4)',
      borderDash: [5, 3],
      backgroundColor: 'transparent',
      fill: false, tension: 0.3,
      pointRadius: 2, pointBackgroundColor: 'rgba(155,89,182,0.4)', borderWidth: 1.5,
    }}
  ];
  sleepChart.options.plugins.legend = {{ display: true, labels: {{ color: '#8b949e', boxWidth: 12 }} }};
  sleepChart.update();

  // --- Sleep Stages stacked bar ---
  const deepHrs = deepMin.map(v => v !== null ? +(v / 60).toFixed(2) : null);
  const remHrs = remMin.map(v => v !== null ? +(v / 60).toFixed(2) : null);
  const lightHrs = lightMin.map(v => v !== null ? +(v / 60).toFixed(2) : null);
  sleepStagesChart.data.labels = labels;
  sleepStagesChart.data.datasets = [
    {{ label: 'Deep', data: deepHrs, backgroundColor: '#1a6bff', borderRadius: 2 }},
    {{ label: 'REM', data: remHrs, backgroundColor: '#a80c7c', borderRadius: 2 }},
    {{ label: 'Light', data: lightHrs, backgroundColor: '#36a5cc', borderRadius: 2 }},
  ];
  sleepStagesChart.options.scales.x.stacked = true;
  sleepStagesChart.options.scales.y.stacked = true;
  sleepStagesChart.options.scales.y.title = {{ display: true, text: 'Hours', color: '#8b949e' }};
  sleepStagesChart.options.plugins.legend = {{ display: true, labels: {{ color: '#8b949e', boxWidth: 12 }} }};
  sleepStagesChart.update();

  // --- Sleep Efficiency chart ---
  efficiencyChart.data.labels = labels;
  efficiencyChart.data.datasets[0].data = sleepEff;
  efficiencyChart.options.scales.y.min = 70;
  efficiencyChart.options.scales.y.max = 100;
  efficiencyChart.update();

  // --- HR chart ---
  hrChart.data.labels = labels;
  hrChart.data.datasets = [
    {{
      label: 'Avg HR', data: hrAvg,
      borderColor: '#ff6b6b', backgroundColor: 'rgba(255,107,107,0.15)',
      fill: false, tension: 0.3, pointRadius: 3, pointBackgroundColor: '#ff6b6b', borderWidth: 2,
    }},
    {{
      label: 'Sleep RHR', data: sleepRhr,
      borderColor: '#9b59b6', borderDash: [5, 3], backgroundColor: 'transparent',
      fill: false, tension: 0.3, pointRadius: 3, pointBackgroundColor: '#9b59b6', borderWidth: 2,
    }},
    {{
      label: 'Max HR', data: hrMax,
      borderColor: 'rgba(255,107,107,0.3)', backgroundColor: 'rgba(255,107,107,0.08)',
      fill: '+1', tension: 0.3, pointRadius: 0, borderWidth: 1,
    }},
    {{
      label: 'Min HR', data: hrMin,
      borderColor: 'rgba(255,107,107,0.3)', backgroundColor: 'transparent',
      fill: false, tension: 0.3, pointRadius: 0, borderWidth: 1,
    }}
  ];
  hrChart.options.plugins.legend = {{ display: true, labels: {{ color: '#8b949e', boxWidth: 12 }} }};
  hrChart.update();

  // --- HRV chart ---
  hrvChart.data.labels = labels;
  hrvChart.data.datasets = [
    {{
      label: 'Daily HRV', data: hrv,
      borderColor: '#4ecdc4', backgroundColor: 'rgba(78,205,196,0.15)',
      fill: true, tension: 0.3, pointRadius: 3, pointBackgroundColor: '#4ecdc4', borderWidth: 2,
    }},
    {{
      label: 'Sleep HRV', data: sleepHrv,
      borderColor: '#88a943', borderDash: [5, 3], backgroundColor: 'transparent',
      fill: false, tension: 0.3, pointRadius: 2, pointBackgroundColor: '#88a943', borderWidth: 1.5,
    }}
  ];
  hrvChart.options.plugins.legend = {{ display: true, labels: {{ color: '#8b949e', boxWidth: 12 }} }};
  hrvChart.update();

  // --- Recovery chart ---
  recoveryChart.data.labels = labels;
  recoveryChart.data.datasets[0].data = recovery;
  recoveryChart.options.scales.y.min = 0;
  recoveryChart.options.scales.y.max = 100;
  recoveryChart.update();

  // --- SpO2 chart ---
  spo2Chart.data.labels = labels;
  spo2Chart.data.datasets[0].data = spo2;
  spo2Chart.options.scales.y.min = 90;
  spo2Chart.options.scales.y.max = 100;
  spo2Chart.update();
}}

document.getElementById('prevMonth').addEventListener('click', () => {{
  if (currentIdx > 0) {{ currentIdx--; updateView(); }}
}});
document.getElementById('nextMonth').addEventListener('click', () => {{
  if (currentIdx < MONTHS.length - 1) {{ currentIdx++; updateView(); }}
}});

if (MONTHS.length > 0) {{
  updateView();
}} else {{
  document.getElementById('monthLabel').textContent = 'No data';
  document.getElementById('statsGrid').innerHTML =
    '<p class="no-data" style="grid-column:1/-1">No historical data available yet.</p>';
}}
</script>
</body>
</html>
"""


def find_latest_chart(prefix: str) -> Path | None:
    """Find the most recently dated chart file matching a prefix."""
    candidates = sorted(OUTPUT_DIR.glob(f"{prefix}_*.png"))
    return candidates[-1] if candidates else None


def find_weekly_charts() -> list[tuple[str, Path]]:
    """Return all weekly chart PNGs for the latest date, ordered current → oldest.

    Filenames follow the convention:
        hr_weekly_YYYYMMDD.png        (week offset 0, this week)
        hr_weekly_YYYYMMDD_w1.png     (1 week ago)
        hr_weekly_YYYYMMDD_w2.png     (2 weeks ago)
        ...
    """
    import re
    all_weekly = list(OUTPUT_DIR.glob("hr_weekly_*.png"))
    if not all_weekly:
        return []

    latest_date = max(
        (m.group(1) for p in all_weekly if (m := re.match(r"hr_weekly_(\d{8})", p.name))),
        default=None,
    )
    if not latest_date:
        return []

    charts: list[tuple[str, Path]] = []
    w0 = OUTPUT_DIR / f"hr_weekly_{latest_date}.png"
    if w0.exists():
        charts.append(("This Week", w0))

    offset_labels = ["1 Week Ago", "2 Weeks Ago", "3 Weeks Ago", "4 Weeks Ago"]
    for i, label in enumerate(offset_labels, start=1):
        wi = OUTPUT_DIR / f"hr_weekly_{latest_date}_w{i}.png"
        if wi.exists():
            charts.append((label, wi))

    return charts


def main():
    parser = argparse.ArgumentParser(description="Build Ultrahuman dashboard HTML pages")
    parser.add_argument("--test", "--dry-run", dest="test_mode", action="store_true",
                        help="Print HTML to stdout instead of writing to _site/")
    parser.add_argument("--data", default=str(DATA_DIR / "last_7_days.json"),
                        help="Input JSON data file (7-day)")
    args = parser.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"Error: Data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    summary = extract_summary(data_path)

    dense_path = find_latest_chart("hr_dense")
    dense_b64 = encode_image(dense_path) if dense_path else None

    weekly_chart_paths = find_weekly_charts()
    weekly_charts = [(label, encode_image(path)) for label, path in weekly_chart_paths]

    if not dense_b64 and not weekly_charts:
        print("Warning: No chart images found in output/. Run hr_charts first.", file=sys.stderr)

    now = datetime.now(LOCAL_TZ)
    updated = now.strftime("%B %-d, %Y at %-I:%M %p %Z")

    # --- Build index (weekly) page ---
    index_html = build_html(summary, dense_b64, weekly_charts, updated)

    # --- Build monthly page ---
    summaries = load_daily_summaries()
    summaries_json = json.dumps(summaries)
    monthly_html = build_monthly_html(summaries_json, updated)

    if args.test_mode:
        print("=== INDEX.HTML ===")
        print(index_html[:500], "...\n")
        print("=== MONTHLY.HTML ===")
        print(monthly_html[:500], "...\n")
        print(f"Summaries: {len(summaries)} days loaded")
    else:
        SITE_DIR.mkdir(exist_ok=True)

        index_path = SITE_DIR / "index.html"
        with open(index_path, "w") as f:
            f.write(index_html)
        print(f"Weekly dashboard written to {index_path}")

        monthly_path = SITE_DIR / "monthly.html"
        with open(monthly_path, "w") as f:
            f.write(monthly_html)
        print(f"Monthly dashboard written to {monthly_path}")

        print(f"  Data range: {summary.get('date_range', 'N/A')}")
        print(f"  HR readings: {summary.get('hr_readings', 0)}")
        print(f"  Dense chart: {dense_path or 'missing'}")
        print(f"  Weekly charts: {len(weekly_charts)} week(s) – {[l for l, _ in weekly_charts]}")
        print(f"  Historical days: {len(summaries)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
