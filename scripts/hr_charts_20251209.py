#!/usr/bin/env python3
"""
Heart Rate Visualization Script
Generates two charts:
1. Most recent 100 intervals at finest granularity (local timezone)
2. 7-day aggregated view with sleep resting HR overlay

Usage:
    python hr_charts_20251209.py
    python hr_charts_20251209.py --test  # Show charts interactively instead of saving
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

# Optional: load from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

# Timezone - detect local or default to US/Pacific
try:
    LOCAL_TZ = ZoneInfo("America/Los_Angeles")  # PST/PDT
except Exception:
    LOCAL_TZ = None  # Fall back to system local


def load_all_data(json_path):
    """
    Load all metrics data from JSON file.
    
    Supports two formats:
      - Dict with data.metrics (single API response)
      - List of {date, data: {data: {metrics: {...}}}} (multi-day query output)
    
    Returns:
        tuple: (hr_df, sleep_df) DataFrames
    """
    with open(json_path, "r") as f:
        data = json.load(f)
    
    # Merge metrics from list-of-days format into a single dict
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
    
    # Extract HR data
    hr_records = []
    for date_str, day_metrics in metrics.items():
        for metric in day_metrics:
            if metric.get("type") == "hr":
                values = metric.get("object", {}).get("values", [])
                for v in values:
                    hr_records.append({
                        "timestamp": v["timestamp"],
                        "value": v["value"],
                        "date": date_str
                    })
    
    hr_df = pd.DataFrame(hr_records)
    if not hr_df.empty:
        # Convert to timezone-aware datetime in local time
        hr_df["datetime"] = pd.to_datetime(hr_df["timestamp"], unit="s", utc=True)
        if LOCAL_TZ:
            hr_df["datetime"] = hr_df["datetime"].dt.tz_convert(LOCAL_TZ)
        else:
            hr_df["datetime"] = hr_df["datetime"].dt.tz_localize(None)  # Use system local
        hr_df = hr_df.sort_values("timestamp").reset_index(drop=True)
    
    # Extract sleep data
    sleep_records = []
    for date_str, day_metrics in metrics.items():
        sleep_rhr = None
        sleep_info = {}
        
        for metric in day_metrics:
            if metric.get("type") == "sleep_rhr":
                sleep_rhr = metric.get("object", {}).get("value")
            elif metric.get("type") == "night_rhr":
                if sleep_rhr is None:
                    sleep_rhr = metric.get("object", {}).get("avg")
            elif metric.get("type") == "sleep":
                obj = metric.get("object", {})
                sleep_info = {
                    "bedtime_start": obj.get("bedtime_start"),
                    "bedtime_end": obj.get("bedtime_end"),
                }
        
        if sleep_rhr is not None:
            sleep_records.append({
                "date": date_str,
                "sleep_rhr": sleep_rhr,
                **sleep_info
            })
    
    sleep_df = pd.DataFrame(sleep_records)
    if not sleep_df.empty:
        sleep_df["date_dt"] = pd.to_datetime(sleep_df["date"])
        if sleep_df["bedtime_start"].notna().any():
            sleep_df["bed_start_dt"] = pd.to_datetime(sleep_df["bedtime_start"], unit="s", utc=True)
            sleep_df["bed_end_dt"] = pd.to_datetime(sleep_df["bedtime_end"], unit="s", utc=True)
            if LOCAL_TZ:
                sleep_df["bed_start_dt"] = sleep_df["bed_start_dt"].dt.tz_convert(LOCAL_TZ)
                sleep_df["bed_end_dt"] = sleep_df["bed_end_dt"].dt.tz_convert(LOCAL_TZ)
    
    return hr_df, sleep_df


def create_dense_chart(hr_df, sleep_df, output_path=None, show=False):
    """
    Create chart of most recent 100 HR intervals with sleep periods marked.
    """
    # Get last 100 readings
    recent = hr_df.tail(100).copy()
    
    if recent.empty:
        print("No HR data available for dense chart")
        return
    
    # Style settings
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(14, 5))
    
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    
    # Find sleep periods that overlap with this time range
    time_min = recent["datetime"].min()
    time_max = recent["datetime"].max()
    
    # Add sleep period shading
    if not sleep_df.empty and "bed_start_dt" in sleep_df.columns:
        for _, row in sleep_df.iterrows():
            if pd.notna(row.get("bed_start_dt")) and pd.notna(row.get("bed_end_dt")):
                bed_start = row["bed_start_dt"]
                bed_end = row["bed_end_dt"]
                # Check if sleep period overlaps with chart range
                if bed_end >= time_min and bed_start <= time_max:
                    ax.axvspan(bed_start, bed_end, alpha=0.15, color="#9b59b6", 
                              label="Sleep Period" if _ == 0 else None)
                    # Add sleep RHR as horizontal line during sleep
                    if pd.notna(row.get("sleep_rhr")):
                        ax.hlines(row["sleep_rhr"], bed_start, bed_end, 
                                 colors="#9b59b6", linestyles="--", linewidth=1.5,
                                 label=f"Sleep RHR" if _ == 0 else None)
    
    # Plot HR line with gradient fill
    ax.plot(recent["datetime"], recent["value"], 
            color="#ff6b6b", linewidth=1.5, alpha=0.9, label="Heart Rate")
    ax.fill_between(recent["datetime"], recent["value"], 
                    alpha=0.3, color="#ff6b6b")
    
    # Add subtle grid
    ax.grid(True, alpha=0.15, color="#ffffff", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Styling
    ax.set_xlabel("Time (Local)", fontsize=11, color="#888888", fontweight="medium")
    ax.set_ylabel("Heart Rate (bpm)", fontsize=11, color="#888888", fontweight="medium")
    ax.set_title("Heart Rate - Last 100 Readings", 
                 fontsize=16, color="#ffffff", fontweight="bold", pad=15)
    
    # Format x-axis for local time
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%I:%M %p"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=0, fontsize=9, color="#888888")
    plt.yticks(fontsize=9, color="#888888")
    
    # Add stats annotation
    stats_text = f"Avg: {recent['value'].mean():.0f} bpm  |  Min: {recent['value'].min():.0f}  |  Max: {recent['value'].max():.0f}"
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, 
            fontsize=10, color="#888888", verticalalignment="top",
            fontfamily="monospace")
    
    # Legend
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(loc="upper right", framealpha=0.3, fontsize=9)
    
    # Spine styling
    for spine in ax.spines.values():
        spine.set_color("#333333")
        spine.set_linewidth(0.5)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, facecolor="#0d1117", edgecolor="none")
        print(f"Saved: {output_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def create_weekly_chart(hr_df, sleep_df, output_path=None, show=False):
    """
    Create 7-day aggregated HR chart with daily stats and sleep RHR overlay.
    """
    if hr_df.empty:
        print("No HR data available for weekly chart")
        return
    
    # Aggregate by date
    daily = hr_df.groupby("date").agg(
        avg=("value", "mean"),
        min=("value", "min"),
        max=("value", "max"),
        std=("value", "std"),
        count=("value", "count")
    ).reset_index()
    daily["date_dt"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date_dt")
    
    # Merge with sleep data
    if not sleep_df.empty:
        daily = daily.merge(sleep_df[["date", "sleep_rhr"]], on="date", how="left")
    else:
        daily["sleep_rhr"] = None
    
    # Take last 7 days
    daily = daily.tail(7)
    
    # Style settings
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 6))
    
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    
    # Plot min-max range as filled area
    ax.fill_between(daily["date_dt"], daily["min"], daily["max"], 
                    alpha=0.2, color="#4ecdc4", label="Awake Min-Max")
    
    # Plot average line
    ax.plot(daily["date_dt"], daily["avg"], 
            color="#4ecdc4", linewidth=2.5, marker="o", markersize=8,
            markerfacecolor="#0d1117", markeredgecolor="#4ecdc4", 
            markeredgewidth=2, label="Awake Average")
    
    # Plot sleep RHR
    if daily["sleep_rhr"].notna().any():
        ax.plot(daily["date_dt"], daily["sleep_rhr"],
                color="#9b59b6", linewidth=2.5, marker="s", markersize=8,
                markerfacecolor="#0d1117", markeredgecolor="#9b59b6",
                markeredgewidth=2, linestyle="--", label="Sleep Resting HR")
        
        # Add sleep RHR labels
        for _, row in daily.iterrows():
            if pd.notna(row["sleep_rhr"]):
                ax.annotate(f'{row["sleep_rhr"]:.0f}', 
                            (row["date_dt"], row["sleep_rhr"]),
                            textcoords="offset points", xytext=(0, -15),
                            ha="center", fontsize=9, color="#9b59b6", fontweight="bold")
    
    # Add awake avg value labels on points
    for _, row in daily.iterrows():
        ax.annotate(f'{row["avg"]:.0f}', 
                    (row["date_dt"], row["avg"]),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=10, color="#ffffff", fontweight="bold")
    
    # Subtle grid
    ax.grid(True, alpha=0.15, color="#ffffff", linestyle="-", linewidth=0.5)
    ax.set_axisbelow(True)
    
    # Styling
    ax.set_xlabel("Date", fontsize=11, color="#888888", fontweight="medium")
    ax.set_ylabel("Heart Rate (bpm)", fontsize=11, color="#888888", fontweight="medium")
    ax.set_title("Heart Rate - 7 Day Overview (Awake + Sleep)", 
                 fontsize=16, color="#ffffff", fontweight="bold", pad=15)
    
    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%b %d"))
    plt.xticks(daily["date_dt"], fontsize=10, color="#888888")
    plt.yticks(fontsize=10, color="#888888")
    
    # Add overall stats
    overall_avg = daily["avg"].mean()
    overall_min = daily["min"].min()
    overall_max = daily["max"].max()
    sleep_avg = daily["sleep_rhr"].mean() if daily["sleep_rhr"].notna().any() else None
    
    stats_text = f"7-Day Awake Avg: {overall_avg:.0f} bpm  |  Range: {overall_min:.0f}-{overall_max:.0f}"
    if sleep_avg:
        stats_text += f"  |  Sleep RHR Avg: {sleep_avg:.0f}"
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes,
            fontsize=10, color="#888888", verticalalignment="top",
            fontfamily="monospace")
    
    # Legend
    ax.legend(loc="upper right", framealpha=0.3, fontsize=9)
    
    # Spine styling
    for spine in ax.spines.values():
        spine.set_color("#333333")
        spine.set_linewidth(0.5)
    
    # Set y-axis limits with padding
    y_vals = list(daily["min"]) + list(daily["max"])
    if daily["sleep_rhr"].notna().any():
        y_vals += list(daily["sleep_rhr"].dropna())
    y_min = min(y_vals) - 5
    y_max = max(y_vals) + 15
    ax.set_ylim(y_min, y_max)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, facecolor="#0d1117", edgecolor="none")
        print(f"Saved: {output_path}")
    
    if show:
        plt.show()
    else:
        plt.close()


def main():
    parser = argparse.ArgumentParser(description="Generate HR visualization charts")
    parser.add_argument("--test", "--dry-run", dest="test_mode", action="store_true",
                        help="Show charts interactively instead of saving")
    parser.add_argument("--input", "-i", default=str(DATA_DIR / "last_7_days.json"),
                        help="Input JSON file path")
    args = parser.parse_args()
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Load data
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Data file not found: {input_path}")
        print("Run the query script first to fetch data.")
        sys.exit(1)
    
    print(f"Loading data from: {input_path}")
    print(f"Using timezone: {LOCAL_TZ or 'system local'}")
    hr_df, sleep_df = load_all_data(input_path)
    print(f"Loaded {len(hr_df)} HR readings, {len(sleep_df)} days of sleep data")
    
    if hr_df.empty:
        print("No heart rate data found in the file.")
        sys.exit(1)
    
    # Generate charts
    print("\nGenerating charts...")
    
    if args.test_mode:
        create_dense_chart(hr_df, sleep_df, show=True)
        create_weekly_chart(hr_df, sleep_df, show=True)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        create_dense_chart(hr_df, sleep_df, OUTPUT_DIR / f"hr_dense_{timestamp}.png")
        create_weekly_chart(hr_df, sleep_df, OUTPUT_DIR / f"hr_weekly_{timestamp}.png")
        print(f"\nCharts saved to: {OUTPUT_DIR}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
