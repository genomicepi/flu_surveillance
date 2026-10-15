"""Render reviewable PNG and SVG examples from fetched CDC CSV files."""
import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np

ROOT = Path(__file__).resolve().parent
BLUE, ORANGE, GRAY = "#176B91", "#C45D32", "#9AA5B1"
MONTH_POSITIONS = [0, 4.5, 8.8, 14, 18.4, 22.4, 26.8, 31.1, 35.5, 39.8, 44.2, 48.6]


def read(label):
    with (ROOT / "data" / f"clinical_national_{label}.csv").open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key, value in row.items():
            try:
                row[key] = float(value)
            except ValueError:
                row[key] = np.nan
    return sorted(rows, key=lambda r: (r["YEAR"], r["WEEK"]))


def slot(week):
    # A dedicated week-53 slot prevents January from shifting between seasons.
    return int(week) - 40 if week >= 40 else int(week) + 13


def series(rows, column):
    values = np.full(53, np.nan)
    for row in rows:
        values[slot(row["WEEK"])] = row[column]
    xs = np.arange(53)
    # A 52-week year has no observation to put in the shared week-53 slot.
    # Omit that x coordinate so the line joins weeks 52 and 1 directly;
    # leave NaNs for genuinely missing observations in existing weeks.
    start_year = min(int(r["YEAR"]) for r in rows)
    has_week_53 = any(int(r["WEEK"]) == 53 for r in rows)
    year_weeks = (week_end(start_year + 1, 1) - week_end(start_year, 1)).days // 7
    if not has_week_53 and year_weeks == 52:
        xs = np.delete(xs, slot(53))
        values = np.delete(values, slot(53))
    return xs, values


def week_end(year, week):
    jan4 = date(int(year), 1, 4)
    sunday = jan4 - timedelta(days=(jan4.weekday() + 1) % 7)
    return sunday + timedelta(weeks=int(week) - 1, days=6)


def style(ax, ylabel):
    ax.set_ylabel(ylabel, labelpad=12)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#CCD3D9")
    ax.grid(axis="y", color="#E5E9EC", linewidth=.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=8)
    ax.set_ylim(bottom=0)


def seasonal_axis(ax, season=None):
    # Approximate month starts on the shared surveillance-week grid. Keep
    # January at week 1 (slot 14), including the dedicated week-53 slot.
    months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    if season:
        year = int(season[:4])
        months[0] += f"\n{year}"
        months[3] += f"\n{year + 1}"
    ax.set_xticks(MONTH_POSITIONS, months)
    ax.set_xlim(-.5, 52.5)
    ax.set_xlabel("Month (approximate)" if season else "Month within each season (approximate)", labelpad=12)


def season_bounds(season):
    year = int(season[:4])
    return week_end(year, 40) - timedelta(days=6), week_end(year + 1, 39)


def current_week_marker(ax, as_of, season, label=True):
    """Mark only a week belonging to the displayed season, on its week grid."""
    first, final = season_bounds(season)
    if not first <= as_of <= final:
        return
    start = as_of - timedelta(days=(as_of.weekday() + 1) % 7)
    end = start + timedelta(days=6)
    year = as_of.year
    if as_of < week_end(year, 1) - timedelta(days=6):
        year -= 1
    elif as_of >= week_end(year + 1, 1) - timedelta(days=6):
        year += 1
    week = (end - week_end(year, 1)).days // 7 + 1
    x = slot(week)
    color = "#7951A0"
    ax.axvline(x, color=color, lw=1.3, linestyle=(0, (3, 3)), alpha=.75, zorder=4)
    if not label:
        return
    dates = f"{start:%b} {start.day}–{end.day}, {end.year}" if start.month == end.month else f"{start:%b %d}–{end:%b %d, %Y}"
    text_x = .45 if x < 26 else .12
    ax.annotate(f"Calendar week\n{dates}\n{season} season", xy=(x, .025),
                xycoords=("data", "axes fraction"), xytext=(text_x, .69),
                textcoords="axes fraction", color=color, fontsize=10, weight="bold",
                ha="left", va="center", zorder=6,
                bbox={"boxstyle": "round,pad=.45", "fc": "white", "ec": "#DDD1E8", "alpha": .96},
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.6,
                            "connectionstyle": "angle,angleA=180,angleB=90,rad=10"})


def save(fig, name, footer):
    fig.text(.09, .025, footer, fontsize=9, color="#596673", va="bottom")
    out = ROOT / "plots"
    out.mkdir(exist_ok=True)
    for ext in ["png", "svg"]:
        fig.savefig(out / f"{name}.{ext}", dpi=180, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", default="2025-26")
    parser.add_argument("--previous", default="2024-25")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("America/Los_Angeles")).date(),
                        help="Date for the calendar-week marker; shown only within the selected season (default: today in Los Angeles)")
    args = parser.parse_args()
    current, previous = read(args.current), read(args.previous)
    last = current[-1]
    cutoff = slot(last["WEEK"])
    ending = week_end(last["YEAR"], last["WEEK"]).strftime("%b %d, %Y")
    retrieved = json.loads((ROOT / "data" / "manifest.json").read_text())["retrieved_at_utc"][:8]
    first, final = season_bounds(args.current)
    status = "Historical season" if args.as_of > final else ("Upcoming season" if args.as_of < first else "Current season")
    marker_note = " Calendar marker is not a reported value." if first <= args.as_of <= final else ""
    source = f"Source: CDC FluView · National clinical laboratories · Retrieved {retrieved[:4]}-{retrieved[4:6]}-{retrieved[6:8]}"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.labelcolor": "#354451", "text.color": "#1D2D3A",
                         "xtick.color": "#596673", "ytick.color": "#596673"})

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [1.25, 1]})
    fig.subplots_adjust(left=.09, right=.96, top=.84, bottom=.20, hspace=.25)
    fig.suptitle(f"Influenza by type | {args.current} season", x=.09, ha="left", y=.97, fontsize=23, weight="bold")
    fig.text(.09, .90, f"{status} · National clinical laboratories · Data through {ending}", color="#596673")
    xs = [slot(r["WEEK"]) for r in current]
    for col, label, color in [("PERCENT POSITIVE", "All influenza (A + B)", "#263A48"), ("PERCENT A", "Influenza A", BLUE), ("PERCENT B", "Influenza B", ORANGE)]:
        axes[0].plot(*series(current, col), label=label, color=color, lw=2.4)
    axes[0].legend(frameon=False, ncol=3, loc="upper right", title="Influenza type · same season")
    axes[1].bar(xs, [r["TOTAL A"] for r in current], width=.85, color=BLUE, label="Influenza A")
    axes[1].bar(xs, [r["TOTAL B"] for r in current], bottom=[r["TOTAL A"] for r in current], width=.85, color=ORANGE, label="Influenza B")
    style(axes[0], "Specimens positive (%)")
    style(axes[1], "Positive specimens")
    axes[1].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    seasonal_axis(axes[1], args.current)
    current_week_marker(axes[0], args.as_of, args.current)
    current_week_marker(axes[1], args.as_of, args.current, label=False)
    save(fig, "01_season_overview", source + "\nCounts are specimens, not unique people; missing weeks are gaps." + marker_note)

    fig, ax = plt.subplots(figsize=(12, 6.8))
    fig.subplots_adjust(left=.09, right=.95, top=.75, bottom=.20)
    fig.suptitle(f"Flu season comparison | {args.current} vs {args.previous}", x=.09, ha="left", y=.97, fontsize=23, weight="bold")
    comparison = next((r for r in previous if r["WEEK"] == last["WEEK"]), None)
    summary = f"{args.current}: {last['PERCENT POSITIVE']:.2f}%"
    if comparison:
        delta = last["PERCENT POSITIVE"] - comparison["PERCENT POSITIVE"]
        summary += f"    |    {args.previous}: {comparison['PERCENT POSITIVE']:.2f}%    |    {delta:+.2f} percentage points"
    fig.text(.09, .89, f"Week ending {ending} · Equivalent week in {args.previous}", color="#596673")
    fig.text(.09, .84, summary, fontsize=12)
    for rows, label, color, width in [(previous, args.previous, GRAY, 2.4), (current, args.current, BLUE, 3)]:
        ax.plot(*series(rows, "PERCENT POSITIVE"), label=label, color=color, lw=width)
    ax.scatter([cutoff], [last["PERCENT POSITIVE"]], color=BLUE, s=50, zorder=5)
    ax.axvline(cutoff, color=BLUE, alpha=.25, lw=1, linestyle=":")
    ax.legend(frameon=False, loc="upper right", title="Season")
    style(ax, "Specimens positive (%)")
    seasonal_axis(ax)
    current_week_marker(ax, args.as_of, args.current)
    save(fig, "02_year_over_year", source + "\nAll influenza (A + B) · Colors identify seasons · Aligned by surveillance week; missing weeks are gaps." + marker_note)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
    fig.subplots_adjust(left=.08, right=.97, top=.76, bottom=.23, wspace=.12)
    fig.suptitle("The mix behind the flu season", x=.08, ha="left", y=.96, fontsize=23, weight="bold")
    fig.text(.08, .87, f"Type-specific positivity · {args.current} versus {args.previous} · Through {ending}", color="#596673")
    for ax, col, title, color in zip(axes, ["PERCENT A", "PERCENT B"], ["Influenza A", "Influenza B"], [BLUE, ORANGE]):
        ax.plot(*series(previous, col), color=GRAY, lw=2.2, label=args.previous)
        ax.plot(*series(current, col), color=color, lw=2.8, label=args.current)
        ax.set_title(title, loc="left", weight="bold", pad=14)
        style(ax, "Specimens positive (%)" if ax is axes[0] else "")
        seasonal_axis(ax)
        ax.tick_params(axis="x", labelsize=9)
        ax.legend(frameon=False, title="Season")
        current_week_marker(ax, args.as_of, args.current)
    save(fig, "03_year_over_year_by_type", source + "\nPanels identify influenza types; lines identify seasons. Percentages use all tested specimens; shared y-scale." + marker_note)
    print(f"Wrote 3 example plots in PNG and SVG to {ROOT / 'plots'}")


if __name__ == "__main__":
    main()
