# Global Market Monitor

[![Tests](https://github.com/Hutch2064/global-market-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/Hutch2064/global-market-monitor/actions/workflows/test.yml)

A global-first daily market tracker for Financial Data Analytics, by Aiden Hutchison. The [live site](https://hutch2064.github.io/global-market-monitor/) has Today, Browse and Trends pages. Funds are proxies: their prices are not spot commodity prices, yields or total returns. Quotes can be delayed or provisional. The daily snapshots are not investment advice.

## Source and selection

The Python pipeline downloads Yahoo Finance chart JSON, once per symbol, using daily observations. New symbols receive a full-history request; subsequent runs request one month, with the original response retained for the full historical record. `catalog.json` lists every retained symbol and its name, category, unit and instrument type; all other symbols are excluded. Global equity and bond funds lead the list, followed by regional funds, commodity proxies, exchange rates, U.S. Treasury yield indexes and market gauges. Yahoo Finance and the relevant exchanges and index providers supply the underlying data. The ICE BofA MOVE index measures implied U.S. Treasury yield volatility; it is a bond-volatility gauge rather than a direct measure of corporate credit spreads. Yahoo mislabels its ^MOVE instrument name; its closing levels have been cross-checked against independent MOVE sources. Nonpositive ^MOVE highs and lows are treated as missing. The author has indicated that Yahoo provided permission for this educational project.

Every successful symbol returns a daily close, high and low. The high and low are retained as two distinct source-reported numeric values, not fabricated changes. Source history is retrieved with an explicit date range, and the pipeline rejects any response that does not report daily granularity. Missing values stay blank. Each symbol is treated as an independent source, so one failure does not stop the others. An unsuccessful source produces no raw file or row that day. A second run on the same UTC date replaces that entire day's raw directory before rebuilding.

## Pipeline and history

`python3 pipeline.py run` downloads the sources, saves their original JSON compressed under `data/raw/YYYY-MM-DD/<URL-encoded-symbol>.json.gz`, rebuilds the files and writes status. `python3 pipeline.py build` rebuilds both CSV files exclusively from the archived raw files, without a network connection. `data/history.csv` has one row per source item and UTC run date, sorted by run date and item ID. It records the most recent observation in that run's source response. `data/source-history.csv` separately contains historical market observations from archived responses; it lets the site show the full source history without pretending that the tracker ran before its first run. Later archives supersede earlier versions of the same market observation, so a rebuild consistently applies the current rules to all retained raw data.

### History columns

| Column | Meaning and unit |
| --- | --- |
| `date` | UTC date of the tracker run, `YYYY-MM-DD` |
| `item_id` | Stable Yahoo symbol |
| `item` | Readable instrument name |
| `source` | Yahoo Finance |
| `category` | Market grouping |
| `unit` | Currency per share, currency per currency, percent or index points, as named |
| `kind` | Fund, currency, yield or index |
| `observation_date` | Exchange-local date of the actual market observation |
| `close` | Source-reported daily closing value in `unit` |
| `high` | Source-reported daily high in `unit`; blank if missing |
| `low` | Source-reported daily low in `unit`; blank if missing |

`data/status.json` contains UTC `run_time`, `first_run_date`, `days_with_success`, `items`, `new_today`, `gone_today`, and `sources` with `name`, `ok` and `count`. New and gone compare source item IDs to the preceding run. The first run reports all items as new. Scheduled checks run at 22:15 and 23:40 UTC; the second skips downloading when a successful scheduled run has already recorded that UTC date. A manual run does not suppress a later scheduled run. Manual dispatch still supports replacing a same-day run. GitHub can delay scheduled jobs, including past midnight UTC. It creates or updates the issue named for the UTC date, closes the previous daily issue, commits the data, and triggers Pages. A run where every source fails is reported as a failed workflow rather than a successful empty archive.

## Calculations

The daily issue ranks up to ten matched items by the absolute percentage change in close since the preceding run: `(new / old - 1) * 100`, with positive endpoints. It includes old and new values and appeared/disappeared items. It is created even if nothing changes.

Today also shows the percentage change since the previous tracker run. The main tables use actual source-observation dates, not fabricated daily observations. 1D and 5D compare one and five observations back; month horizons use the latest observation on or before the calendar boundary; YTD uses the last observation before January 1; All uses the first valid observation. Percentage changes require positive endpoints. A 52-week high/low is the highest/lowest daily **close** in the 364-day window and is blank without a complete window of history. Annualized volatility is the sample standard deviation of consecutive positive daily close-to-close percentage changes multiplied by the square root of 252. It uses the full available history and is blank with fewer than two valid changes. Prices are unadjusted and can be affected by distributions and splits; relative yield changes are not bond returns. The site displays source observation dates and a dash when a calculation is unavailable.

Trends uses `data/history.csv` for its run-history charts and four findings. The long-term source-history chart on Browse uses `data/source-history.csv`. Findings recalculate in the browser; early results need more than one daily run to be informative. Today and Browse compute table statistics from the separately identified source history. The browser loads files over the network when online; the service worker caches the app and successfully loaded data for offline reuse.

## Local development

```sh
python3 -m pip install pytest
python3 -m pytest -q
python3 -m http.server 8000
```

Open `http://localhost:8000/`. A public GitHub repository with Pages enabled and Actions permissions for contents, issues and workflows is required for automated publication. The assignment requires successful runs on at least seven different UTC dates; a first successful run alone does not satisfy that condition.

## File map

- `pipeline.py`: acquisition, raw archive, conversion, history rebuild and status.
- `issue.py`: ranked report and date-based GitHub Issue create/update/close.
- `catalog.json`: retained source symbols and metadata.
- `metrics.py`: reference Python implementation of the displayed calculations.
- `tests/test_metrics.py`, `tests/test_pipeline.py`: calculation, conversion, movement and same-day rebuild tests.
- `.github/workflows/daily.yml`: daily job, issue update and data commit.
- `.github/workflows/test.yml`: pytest on every push and pull request.
- `.github/workflows/pages.yml`: GitHub Pages deployment.
- `data/raw/`: compressed unmodified source responses by UTC run date.
- `data/history.csv`, `data/status.json`: required tracker data.
- `data/source-history.csv`: separately identified long-term observations.
- `index.html`, `browse.html`, `trends.html`: three required pages.
- `app.js`, `style.css`: browser calculations, interactions and shared visual design.
- `manifest.webmanifest`, `sw.js`, `icon.svg`, `icon-192.png`, `icon-512.png`: install and offline support.
- `SUBMISSION.txt`: four-line course submission.
- `.gitignore`, `README.md`: local exclusions and documentation.
