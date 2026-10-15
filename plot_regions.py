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


def main():
    manifest = json.loads((ROOT / 'data/regions/manifest.json').read_text())
    out = ROOT / 'plots/hhs_regions'
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                         'text.color': '#1D2D3A', 'axes.labelcolor': '#354451',
                         'xtick.color': '#596673', 'ytick.color': '#596673'})
    for entry in manifest['regions']:
        dates, values = regional_rows(entry, manifest)
        fig, axes = plt.subplots(2, 1, figsize=(13, 8.5), sharex=True)
        fig.subplots_adjust(left=.09, right=.96, top=.78, bottom=.23, hspace=.40)
        fig.suptitle(f"HHS Region {entry['number']} | {', '.join(entry['abbreviations'])}",
                     x=.09, y=.96, ha='left', fontsize=23, weight='bold')
        fig.text(.09, .885, 'Influenza positive tests reported by clinical laboratories', fontsize=15)
        fig.text(.09, .855, f"{manifest['seasons'][0]} season with prior-season context · "
                 f"{dates[0]:%b %d, %Y} – {dates[-1]:%b %d, %Y}", fontsize=11, color='#596673')
        axes[0].bar(dates, values['TOTAL A'], width=5.8, color=BLUE, label='Influenza A')
        axes[0].bar(dates, values['TOTAL B'], bottom=values['TOTAL A'],
                    width=5.8, color=ORANGE, label='Influenza B')
        style(axes[0], 'Positive specimens')
        axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f'{value:,.0f}'))
        axes[0].set_title('Positive test counts', loc='left', fontsize=12, weight='bold')
        axes[0].legend(frameon=False, ncol=2, loc='upper right')
        for col, label, color in [('PERCENT POSITIVE', 'All influenza (A + B)', '#263A48'),
                                   ('PERCENT A', 'Influenza A', BLUE), ('PERCENT B', 'Influenza B', ORANGE)]:
            axes[1].plot(dates, values[col], color=color, lw=2.1, label=label)
        style(axes[1], 'Specimens positive (%)')
        axes[1].set_title('Test positivity', loc='left', fontsize=12, weight='bold')
        axes[1].legend(frameon=False, ncol=3, loc='upper right', fontsize=10)
        axes[1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%b\n%Y'))
        axes[1].set_xlabel('Week ending', labelpad=10)
        axes[1].set_xlim(dates[0] - timedelta(days=5), dates[-1] + timedelta(days=5))
        # Season boundary comes from CDC's week metadata, not an assumed October date.
        boundary = next(date.fromisoformat(w['weekstart']) for w in manifest['weeks']
                        if w['year'] == int(manifest['seasons'][0][:4]) and w['weeknumber'] == 40)
        for ax in axes:
            if dates[0] < boundary < dates[-1]:
                ax.axvline(boundary, color='#9AA5B1', linestyle=':', lw=1)
            ax.axvline(dates[-1], color='#9AA5B1', linestyle=':', lw=1)
            ax.margins(y=.20)
        if dates[0] < boundary < dates[-1]:
            axes[0].text(boundary + timedelta(days=5), .98, f"{manifest['seasons'][0]} begins",
                         transform=axes[0].get_xaxis_transform(), va='top', fontsize=9, color='#596673')
        stamp = manifest['retrieved_at_utc']
        fig.text(.09, .025, f"Source: CDC FluView · HHS regional clinical laboratories · Retrieved {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}\n"
                 'Counts are specimens, not unique people. All positivity percentages use total tested specimens.\n'
                 'Titles list CDC FluView region members; city reporting areas are included under their state. Missing observations remain gaps.',
                 fontsize=9, color='#596673', linespacing=1.6, va='bottom')
        for ext in ['png', 'svg']:
            fig.savefig(out / f"hhs_region_{entry['number']:02}.{ext}", dpi=180, facecolor='white')
        plt.close(fig)
    print('Wrote ten two-panel HHS regional figures in PNG and SVG')


if __name__ == '__main__':
    main()
