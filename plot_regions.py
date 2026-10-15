"""Render two-panel HHS regional figures on a continuous weekly timeline."""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter
import numpy as np

from plot import BLUE, ORANGE, style

ROOT = Path(__file__).resolve().parent


def regional_rows(entry, manifest):
    calendar = {(w['year'], w['weeknumber']): w for w in manifest['weeks']}
    previous = manifest['seasons'][1]
    # Match the live CDC chart: begin with week 21 of the preceding season.
    start = next(date.fromisoformat(w['weekend']) for w in manifest['weeks']
                 if w['year'] == int(previous[:4]) + 1 and w['weeknumber'] == 21)
    dated = {}
    for download in entry['downloads']:
        with (ROOT / 'data/regions' / download['file']).open() as f:
            for row in csv.DictReader(f):
                key = (int(row['YEAR']), int(row['WEEK']))
                ending = date.fromisoformat(calendar[key]['weekend'])
                if ending < start:
                    continue
                if ending in dated:
                    raise ValueError(f'Duplicate regional week-ending date: {ending}')
                values = {}
                for key, value in row.items():
                    try:
                        values[key] = float(value)
                    except ValueError:
                        values[key] = np.nan
                dated[ending] = values
    if not dated:
        raise ValueError('No regional observations in the selected time window')
    last = max(dated)
    dates = [start + timedelta(weeks=i) for i in range((last - start).days // 7 + 1)]
    # Nonexistent week 53 adds no gap; real missing weeks retain NaNs.
    return dates, {col: np.array([dated.get(day, {}).get(col, np.nan) for day in dates])
                   for col in ['TOTAL A', 'TOTAL B', 'PERCENT POSITIVE', 'PERCENT A', 'PERCENT B']}


def comparison_week(dates, manifest):
    """Match the reported surveillance week in the preceding year, not 365 days."""
    latest = next(w for w in manifest['weeks'] if w['weekend'] == dates[-1].isoformat())
    prior = next((w for w in manifest['weeks']
                  if w['year'] == latest['year'] - 1 and w['weeknumber'] == latest['weeknumber']), None)
    prior_date = date.fromisoformat(prior['weekend']) if prior else None
    index = dates.index(prior_date) if prior_date in dates else None
    return latest['weeknumber'], index


def annotate_comparison(ax, dates, values, week, prior_index, percent=False):
    for index, label, position, align, color in [
        (prior_index, 'Same week last year', (.02, .52), 'left', '#7951A0'),
        (len(dates) - 1, 'Latest reported week', (.98, .34), 'right', '#263A48'),
    ]:
        if index is None:
            ax.text(.02, .52, f'Same week last year\nWeek {week}: unavailable',
                    transform=ax.transAxes, fontsize=10, color=color)
            continue
        value = values[index]
        if label == 'Latest reported week' and np.isfinite(value) and value > ax.get_ylim()[1] * .25:
            position = (.98, .82)
        formatted = (f'{value:.2f}%' if percent else f'{value:,.0f} positive specimens') if np.isfinite(value) else 'No reported value'
        text = f'{label}\nWeek {week} · {dates[index]:%b %d, %Y}\n{formatted}'
        if not np.isfinite(value):
            ax.text(*position, text, transform=ax.transAxes, ha=align, fontsize=10, color=color)
            continue
        ax.scatter([dates[index]], [value], s=42, color=color, edgecolor='white', linewidth=.8, zorder=6)
        ax.annotate(text, xy=(mdates.date2num(dates[index]), value),
                    xytext=position, textcoords='axes fraction', ha=align, va='center',
                    fontsize=10, color=color, linespacing=1.5,
                    bbox={'boxstyle': 'round,pad=.4', 'fc': 'white', 'ec': '#DDE2E7', 'alpha': .97},
                    arrowprops={'arrowstyle': '-|>', 'color': color, 'lw': 1.3}, zorder=7)


def main():
    manifest = json.loads((ROOT / 'data/regions/manifest.json').read_text())
    out = ROOT / 'plots/hhs_regions'
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'text.color': '#1D2D3A', 'axes.labelcolor': '#354451',
                         'xtick.color': '#596673', 'ytick.color': '#596673'})
    for entry in manifest['regions']:
        dates, values = regional_rows(entry, manifest)
        fig, axes = plt.subplots(1, 2, figsize=(14, 8.5), sharex=True)
        fig.subplots_adjust(left=.07, right=.97, top=.71, bottom=.23, wspace=.25)
        fig.suptitle(f"HHS Region {entry['number']} | {', '.join(entry['abbreviations'])}",
                     x=.07, y=.96, ha='left', fontsize=23, weight='bold')
        fig.text(.07, .885, 'Influenza positive tests reported by clinical laboratories', fontsize=15)
        fig.text(.07, .855, f"{manifest['seasons'][0]} season with prior-season context · "
                 f"{dates[0]:%b %d, %Y} – {dates[-1]:%b %d, %Y}", fontsize=11, color='#596673')
        axes[0].bar(dates, values['TOTAL A'], width=5.8, color=BLUE, label='Influenza A')
        axes[0].bar(dates, values['TOTAL B'], bottom=values['TOTAL A'],
                    width=5.8, color=ORANGE, label='Influenza B')
        style(axes[0], 'Positive specimens')
        axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:,.0f}'))
        axes[0].set_title('Positive test counts', loc='left', fontsize=13, weight='bold', pad=52)
        axes[0].legend(frameon=False, ncol=2, loc='lower left', bbox_to_anchor=(0, 1.015), fontsize=10)
        for col, label, color in [('PERCENT POSITIVE', 'All influenza (A + B)', '#263A48'),
                                   ('PERCENT A', 'Influenza A', BLUE), ('PERCENT B', 'Influenza B', ORANGE)]:
            axes[1].plot(dates, values[col], color=color, lw=2.1, label=label, marker='o', markersize=2.5)
        style(axes[1], 'Specimens positive (%)')
        axes[1].set_title('Test positivity', loc='left', fontsize=13, weight='bold', pad=52)
        axes[1].legend(frameon=False, ncol=3, loc='lower left', bbox_to_anchor=(0, 1.015), fontsize=8, columnspacing=1)
        week, prior_index = comparison_week(dates, manifest)
        for ax in axes:
            ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
            ax.set_xlabel('Week ending', labelpad=10)
            ax.set_xlim(dates[0] - timedelta(days=7), dates[-1] + timedelta(days=10))
        annotate_comparison(axes[0], dates, values['TOTAL A'] + values['TOTAL B'], week, prior_index)
        annotate_comparison(axes[1], dates, values['PERCENT POSITIVE'], week, prior_index, percent=True)
        stamp = manifest['retrieved_at_utc']
        fig.text(.07, .025, f"Source: CDC FluView · HHS regional clinical laboratories · Retrieved {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}\n"
                 'Counts are specimens, not unique people. All positivity percentages use total tested specimens.\n'
                 'Callouts compare the same surveillance week in each year: total A + B specimens (left), overall positivity (right). Missing observations remain gaps.',
                 fontsize=9, color='#596673', linespacing=1.6, va='bottom')
        for ext in ['png', 'svg']:
            fig.savefig(out / f"hhs_region_{entry['number']:02}.{ext}", dpi=180, facecolor='white')
        plt.close(fig)
    print('Wrote ten two-panel HHS regional figures in PNG and SVG')


if __name__ == '__main__':
    main()
