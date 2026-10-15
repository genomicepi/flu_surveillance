# Flu surveillance

National clinical-laboratory influenza data from the CDC FluView chart, plus the CDC ILINet state/jurisdiction activity map, exported as PNG and SVG. Ten regional figures show clinical test counts and positivity in separate panels.

## Run

Python 3.12 is used by the automated workflow. Clone the repository and install dependencies in a virtual environment:

```sh
git clone https://github.com/genomicepi/flu_surveillance.git
cd flu_surveillance
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python update.py
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.

`fetch.py` without arguments retrieves the latest two enabled seasons from CDC metadata. `update.py` automatically passes the downloaded seasons to the plotting script. When running `plot.py` separately, use `--current` and `--previous` to select seasons; its defaults are 2025–26 and 2024–25. The GitHub Actions workflow refreshes daily at 18:23 UTC and can also be run manually.

The purple “Calendar week” annotation appears only when the `--as-of` date falls within the selected `--current` season (CDC weeks 40 through 39). It uses the same surveillance-week grid as the data and identifies calendar timing, not a reported value. Historical-season plots omit it. By default the date is today in America/Los_Angeles; `--as-of YYYY-MM-DD` supports reproducible renders.

The overview shows one season: colors distinguish influenza A, influenza B, and their combined positivity. Its timeline labels include the calendar years, and its subtitle identifies historical seasons. In comparison plots, lines identify seasons; the type-specific comparison separates A and B into labeled panels. Comparison axes show months within each season rather than a single calendar year.

## Automated updates

Run `python update.py` to fetch the latest two enabled seasons and plot that exact pair, including season rollover. It also fetches the latest published state/jurisdiction ILI activity week and renders the map. The two sources select their latest available weeks independently; each figure labels its own data date. The GitHub Actions workflow runs on Ubuntu daily at 18:23 UTC, on relevant pushes to `main`, or via **Actions → Update flu surveillance → Run workflow**.

Each CDC response logs its HTTP status, method, and URL. HTTP errors also log a short response-body excerpt. A 403 fails the run without retrying that status or committing outputs. Successful runs commit refreshed data, archived snapshots, and plots to `main`. Each run uploads a 30-day artifact containing the log and available data/plots, even on failure; files in a failed run's artifact may be from the previous successful refresh, so check the manifest timestamp and log.

## Outputs

- `data/clinical_national_SEASON.csv`: latest downloaded season data.
- `data/manifest.json`: retrieval timestamp, selections, endpoint and row counts.
- `data/snapshots/TIMESTAMP/`: raw season CSVs, CDC metadata and retrieval manifest.
- `plots/01_season_overview.{png,svg}`: positivity lines and a separate stacked specimen-count panel.
- `plots/02_year_over_year.{png,svg}`: positivity comparison and the latest equivalent-week difference in percentage points.
- `plots/03_year_over_year_by_type.{png,svg}`: A and B positivity comparisons with a shared scale.
- `data/ili_latest.{json,csv}`: latest ILI activity levels, week, and jurisdiction data; JSON includes source metadata, colors, and report URL.
- `data/ili_snapshots/TIMESTAMP/`: archived raw CDC ILI response and normalized map data.
- `plots/04_ili_activity_map.{png,svg}`: latest state/jurisdiction ILI activity map using CDC colors and inset boundaries.

- `data/regions/clinical_hhs_NN_SEASON.csv`: clinical data for all ten HHS regions and latest two seasons.
- `data/regions/manifest.json`: regional requests, membership, source week dates, and retrieval timestamp.
- `data/regions/snapshots/TIMESTAMP/`: archived regional CSVs and metadata.
- `plots/hhs_regions/hhs_region_NN.{png,svg}`: one two-panel clinical-laboratory figure per HHS region.

## Source and interpretation

Current report entrypoint: https://www.cdc.gov/fluview/surveillance/index.html

**Downloads are not pinned to a report-page URL.** Laboratory seasons come from live backend metadata. The map uses the latest week with activity records in the live ILI response. The corresponding week-specific report URLs are generated from the returned year/week and recorded in `data/manifest.json` and `data/ili_latest.json`; these are reference links, not ingestion inputs. A report link can lag backend publication and is not a guaranteed archive of the downloaded values.

The map embedded in a dated CDC report can include `mmwrid` and `seasonid` query parameters that pin it to that report's week. Our map does not reuse those fixed parameters. It updates automatically as CDC publishes new weeks and seasons.

Embedded chart: https://gis.cdc.gov/grasp/fluview/FluPortalDashboardWidget_CL.html

The fetcher uses the same public backend as the chart download button. This is a website implementation endpoint, not a guaranteed versioned API. It resolves season IDs through `GetPhase02InitApp`, then requests `PostPhase02StackedColumnChartDataDownload` with national geography and clinical laboratories. It checks the CSV schema, week uniqueness, numerical ranges and specimen totals before replacing the current files, and retries transient HTTP failures.

Counts are specimens, not unique patients or population incidence. Overall, A and B positivity each use total tested specimens as the denominator. Positivity is more suitable than raw counts for this comparison, but changes in testing practices or participating laboratories can still affect it.

Seasons are aligned by CDC surveillance week: 40 through 52, a dedicated week-53 slot, then 1 through 39. The visible axes show approximate months, October through September, while retaining that weekly alignment. Month ticks are approximate because calendar dates differ between seasons. For 52-week years, lines connect directly from week 52 to week 1 across the unused week-53 slot. Actual missing observations remain gaps, not zeros or interpolated observations. The latest comparison uses the same surveillance week in both seasons. Week-ending dates use the MMWR Sunday–Saturday convention, with week 1 containing January 4.

The laboratory chart embedded in the report uses a live backend without an archive-date parameter. A current laboratory-data download need not reproduce the values originally shown on an older report. Refresh entire seasons to capture revisions, and retain snapshots to preserve each retrieval. The plotted retrieval date identifies the source snapshot, not the report publication date.

## ILI activity map

`fetch_map.py` reads `https://gis.cdc.gov/FluView1/Phase1IniP`, the public data source used by the CDC ILI widget. It joins activity records to CDC jurisdiction, week, season, and intensity metadata, validates duplicate jurisdictions and activity ranges, and archives the raw response. `plot_map.py` uses the returned colors and activity categories directly. It fails if a reporting jurisdiction has no map geometry, rather than silently omitting it. Boundaries are a locally stored copy of CDC's inset TopoJSON (see `assets/SOURCE.md`).

The map is a static state/jurisdiction view, including New York City and available territories; CBSA maps and week playback are not included. White represents insufficient data or a geography absent from the latest response. ILI measures outpatient visits for fever plus cough or sore throat, not laboratory-confirmed influenza. Other respiratory pathogens can contribute; the activity level does not measure the geographic spread of influenza. See [CDC surveillance methods](https://www.cdc.gov/fluview/overview/index.html).

## HHS regional figures

The daily update also runs `fetch_regions.py` and `plot_regions.py`. Each figure has stacked influenza A/B positive specimen counts above and all-influenza, A, and B positivity lines below, with a shared chronological date axis and no dual axis. Colors match the national figures. Axis ranges adapt to each region; compare the labeled values rather than bar heights across separate figures.

The time window follows the CDC live clinical chart: week 21 of the preceding season through the latest available week. Week-ending dates come from CDC's `PostPhase02WHOGetData` metadata. This preserves chronological continuity through year boundaries without an artificial week-53 gap; real missing observations remain gaps. The latest data date appears in the subtitle, and the beginning of the newer season is marked on both panels. Calendar-time arrows are omitted from these historical views.

Titles abbreviate the membership returned by CDC FluView's `hhsregionstates` metadata. New York City, Chicago, and Los Angeles are folded into NY, IL, and CA. PR, VI, and GU identify territories where included by CDC. These labels describe the FluView reporting regions, not every jurisdiction administered by an [HHS regional office](https://www.hhs.gov/about/agencies/iea/regional-offices/index.html); for example, the broader administrative Region 9 includes additional Pacific jurisdictions. A region label does not imply that every jurisdiction or laboratory submitted data for every week.

Run `python fetch_regions.py` followed by `python plot_regions.py` to refresh only the regional figures. Run `python -m unittest discover` for the data selection and timeline regression checks.
