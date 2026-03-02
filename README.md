# Ultrahuman Data Query Tools

> **Note**: This page was built by an AI assistant. Last updated 2026-03-02.

Scripts for querying and visualizing personal health data from the Ultrahuman Vision API. A GitHub Pages dashboard is updated nightly via GitHub Actions.

https://sugarsmax.github.io/ultrahuman/

## Project Structure

```
ultrahuman/
  .github/workflows/
    nightly_update.yml                    # Nightly CI: fetch, chart, deploy
  scripts/
    ultrahuman_query_20251209.py          # API query script
    hr_charts_20251209.py                 # Heart rate visualization script
    extract_daily_summaries_20260302.py   # Daily summary extractor + merger
    build_page_20260302.py                # HTML dashboard generator (weekly + monthly)
  config/
    env_template.txt                      # Environment variable reference
  data/
    daily_summaries.json                  # Long-term archive, git-committed
    last_7_days.json                      # Ephemeral API response (gitignored)
  output/                                 # Chart images (auto-created)
  _site/                                  # Generated dashboard (gitignored, built by CI)
    index.html                            # Weekly view (base64 charts)
    monthly.html                          # Monthly view (Chart.js + inline JSON)
  requirements.txt
  .gitignore
```

## Setup

### 1. Activate Shared Virtual Environment

This project uses the shared venv. All required packages are already installed there.

```bash
source ~/.python-venvs/pdms-shared/bin/activate
```

> `python-dotenv` is not in the shared venv, but the scripts handle that gracefully -- they fall back to reading environment variables directly. If you prefer auto-loading from `.env`, install it: `pip install python-dotenv`

### 2. Get API Token

1. Go to <a href="https://vision.ultrahuman.com/developer/docs" target="_blank">Ultrahuman Vision Developer Portal</a>
2. Generate a Personal API Token with "Ring Data Access" scope
3. Complete the 6-character passcode linking in your Ultrahuman Ring mobile app

### 3. Create `.env` File

Create a `.env` file in the project root (it's gitignored). See `config/env_template.txt` for the full reference.

```bash
ULTRAHUMAN_API_TOKEN=your_jwt_token_here
ULTRAHUMAN_EMAIL=your_email@example.com
```

## Usage

### Query Today's Metrics

```bash
source ~/.python-venvs/pdms-shared/bin/activate
python scripts/ultrahuman_query_20251209.py
```

### Query a Specific Date

```bash
python scripts/ultrahuman_query_20251209.py --date 2025-12-08
```

### Query a Date Range

```bash
python scripts/ultrahuman_query_20251209.py --start-date 2025-12-01 --end-date 2025-12-09
```

### Dry Run / Test Mode

```bash
python scripts/ultrahuman_query_20251209.py --test
```

### Continue from Last Query

```bash
python scripts/ultrahuman_query_20251209.py --continue
```

### Save Output to File

```bash
python scripts/ultrahuman_query_20251209.py --output data/metrics.json
```

## Heart Rate Charts

The `hr_charts_20251209.py` script generates two visualizations from previously queried data (`data/last_7_days.json`):

1. **Recent 100 intervals** -- finest-granularity HR at local timezone (PST/PDT)
2. **7-day aggregated view** -- daily HR range with sleep resting HR overlay

### Generate Charts (saved to `output/`)

```bash
python scripts/hr_charts_20251209.py
```

### Interactive Preview (test mode)

```bash
python scripts/hr_charts_20251209.py --test
```

## API Reference

- **Base URL**: `https://partner.ultrahuman.com`
- **Endpoint**: `/api/v1/partner/daily_metrics`
- **Auth Header**: `Authorization: YOUR_TOKEN` (no Bearer prefix)
- **Docs**: <a href="https://vision.ultrahuman.com/developer/docs" target="_blank">Ultrahuman Vision Developer Docs</a>

## Data Architecture

### Two-tier storage

| File | Purpose | Git status |
|------|---------|------------|
| `data/last_7_days.json` | Raw API response for dense HR charts | gitignored, ephemeral |
| `data/daily_summaries.json` | One record per day, long-term archive (up to 3 years) | **committed** |

The `daily_summaries.json` file is append-only. Each nightly run extracts per-day aggregates (avg/min/max HR, sleep RHR, HRV, recovery, sleep hours) from the 7-day fetch and merges them in. Duplicate dates are overwritten with the latest data.

### Extract daily summaries manually

```bash
python scripts/extract_daily_summaries_20260302.py --input data/last_7_days.json
python scripts/extract_daily_summaries_20260302.py --test  # dry run
```

## Data Log

Historical metrics are also tracked in a <a href="https://docs.google.com/spreadsheets/d/1jbRvJd_4-dtYEwhZU8C__b02Qe5WNgMq692JyxvwF8E/edit?gid=0#gid=0" target="_blank">Google Sheets spreadsheet</a>.

## GitHub Pages Dashboard

Two pages are built nightly and deployed to GitHub Pages:

- **Weekly** (`index.html`) -- 7-day view with embedded matplotlib chart PNGs
- **Monthly** (`monthly.html`) -- month-selectable view with Chart.js trend lines, reading from the long-term `daily_summaries.json` archive

### Automatic (nightly)

The GitHub Actions workflow runs at midnight Pacific every night:
1. Fetches the last 7 days of metrics from the Ultrahuman API
2. Generates dense and weekly HR chart PNGs
3. Extracts daily summaries and merges into `data/daily_summaries.json`
4. Commits the updated summaries file back to the repo
5. Builds `_site/index.html` and `_site/monthly.html`
6. Deploys to GitHub Pages

You can also trigger a manual run from the **Actions** tab.

### First-time repo setup

1. Push this repo to GitHub (e.g. `git remote add origin git@github.com:<user>/ultrahuman.git`)
2. Go to **Settings > Pages** and set Source to **GitHub Actions**
3. Go to **Settings > Secrets and variables > Actions** and add:
   - `ULTRAHUMAN_API_TOKEN` -- your Ultrahuman API JWT
   - `ULTRAHUMAN_EMAIL` -- your Ultrahuman account email
4. Trigger the workflow manually or wait for the nightly run

### Build locally

```bash
source ~/.python-venvs/pdms-shared/bin/activate
python scripts/ultrahuman_query_20251209.py --start-date 2026-02-23 --end-date 2026-03-01 --output data/last_7_days.json
python scripts/hr_charts_20251209.py --input data/last_7_days.json
python scripts/extract_daily_summaries_20260302.py --input data/last_7_days.json
python scripts/build_page_20260302.py
open _site/index.html
open _site/monthly.html
```

## Data Available

The API returns daily metrics including:
- Heart rate (hr) -- timestamped values throughout the day
- HRV (heart rate variability)
- Sleep data (bedtime start/end, sleep resting HR)
- Recovery scores
- Activity/movement data

---

*Built with Claude claude-4.6-opus*

