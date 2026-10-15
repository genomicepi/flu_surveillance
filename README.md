# Flu surveillance

National clinical-laboratory influenza data from the CDC FluView chart, with three example figures exported as PNG and SVG.

## Run

```sh
cd /Users/kja/Documents/GitHub/flu_surveillance
python3 -m pip install -r requirements.txt
python3 fetch.py --seasons 2025-26 2024-25
python3 plot.py --current 2025-26 --previous 2024-25
```

`fetch.py` without arguments retrieves the latest two enabled seasons from CDC metadata. Plot season arguments default to the initial review pair, 2025–26 and 2024–25; change them when the season rolls over. The GitHub Actions workflow refreshes daily at 18:23 UTC and can also be run manually.

The purple “Calendar week” annotation appears only when the `--as-of` date falls within the selected `--current` season (CDC weeks 40 through 39). It uses the same surveillance-week grid as the data and identifies calendar timing, not a reported value. Historical-season plots omit it. By default the date is today in America/Los_Angeles; `--as-of YYYY-MM-DD` supports reproducible renders.

The overview shows one season: colors distinguish influenza A, influenza B, and their combined positivity. Its timeline labels include the calendar years, and its subtitle identifies historical seasons. In comparison plots, lines identify seasons; the type-specific comparison separates A and B into labeled panels. Comparison axes show months within each season rather than a single calendar year.

## Automated updates

Run `python update.py` to fetch the latest two enabled seasons and plot that exact pair, including season rollover. The GitHub Actions workflow runs on Ubuntu daily at 18:23 UTC, on relevant pushes to `main`, or via **Actions → Update flu surveillance → Run workflow**.

Each CDC response logs its HTTP status, method, and URL. HTTP errors also log a short response-body excerpt. A 403 fails the run without retrying that status or committing outputs. Successful runs commit refreshed data, archived snapshots, and plots to `main`. Each run uploads a 30-day artifact containing the log and available data/plots, even on failure; files in a failed run's artifact may be from the previous successful refresh, so check the manifest timestamp and log.

## Outputs

- `data/clinical_national_SEASON.csv`: latest downloaded season data.
- `data/manifest.json`: retrieval timestamp, selections, endpoint and row counts.
- `data/snapshots/TIMESTAMP/`: raw season CSVs, CDC metadata and retrieval manifest.
- `plots/01_season_overview.{png,svg}`: positivity lines and a separate stacked specimen-count panel.
- `plots/02_year_over_year.{png,svg}`: positivity comparison and the latest equivalent-week difference in percentage points.
- `plots/03_year_over_year_by_type.{png,svg}`: A and B positivity comparisons with a shared scale.

## Source and interpretation

Source report: https://www.cdc.gov/fluview/surveillance/2026-week-38.html

Embedded chart: https://gis.cdc.gov/grasp/fluview/FluPortalDashboardWidget_CL.html

The fetcher uses the same public backend as the chart download button. This is a website implementation endpoint, not a guaranteed versioned API. It resolves season IDs through `GetPhase02InitApp`, then requests `PostPhase02StackedColumnChartDataDownload` with national geography and clinical laboratories. It checks the CSV schema, week uniqueness, numerical ranges and specimen totals before replacing the current files, and retries transient HTTP failures.

Counts are specimens, not unique patients or population incidence. Overall, A and B positivity each use total tested specimens as the denominator. Positivity is more suitable than raw counts for this comparison, but changes in testing practices or participating laboratories can still affect it.

Seasons are aligned by CDC surveillance week: 40 through 52, a dedicated week-53 slot, then 1 through 39. The visible axes show approximate months, October through September, while retaining that weekly alignment. Month ticks are approximate because calendar dates differ between seasons. For 52-week years, lines connect directly from week 52 to week 1 across the unused week-53 slot. Actual missing observations remain gaps, not zeros or interpolated observations. The latest comparison uses the same surveillance week in both seasons. Week-ending dates use the MMWR Sunday–Saturday convention, with week 1 containing January 4.

The report embeds a live chart without an archive-date parameter. A current download need not reproduce the values originally shown on an older report. Refresh entire seasons to capture revisions, and retain snapshots to preserve each retrieval. The plotted retrieval date identifies the source snapshot, not the report publication date.
