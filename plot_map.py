"""Render CDC state/jurisdiction ILI activity using CDC's inset map geometry."""
import json
from collections import Counter
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch, Rectangle
import numpy as np

ROOT = Path(__file__).resolve().parent


def project(points):
    # Spherical Albers equal-area, matching the widget's D3 Albers parallels.
    coords = np.radians(np.asarray(points))
    phi1, phi2 = np.radians([29.5, 45.5])
    n = (np.sin(phi1) + np.sin(phi2)) / 2
    c = np.cos(phi1)**2 + 2 * n * np.sin(phi1)
    rho = np.sqrt(c - 2 * n * np.sin(coords[:, 1])) / n
    theta = n * (coords[:, 0] + np.radians(96))
    return np.column_stack([rho * np.sin(theta), -rho * np.cos(theta)])


def decode_geometries(topology):
    scale, translate = topology['transform']['scale'], topology['transform']['translate']
    arcs = [np.cumsum(arc, axis=0) * scale + translate for arc in topology['arcs']]
    for geom in topology['objects']['State_Territory_FluView1']['geometries']:
        polygons = [geom['arcs']] if geom['type'] == 'Polygon' else geom['arcs']
        rings = []
        for polygon in polygons:
            for ring in polygon:
                pieces = [arcs[index] if index >= 0 else arcs[~index][::-1] for index in ring]
                joined = np.concatenate([pieces[0]] + [piece[1:] for piece in pieces[1:]])
                rings.append(project(joined))
        yield geom['properties'], rings


def main():
    data = json.loads((ROOT / 'data/ili_latest.json').read_text())
    topology = json.loads((ROOT / 'assets/ili_states.topojson').read_text())
    rows = {row['fips']: row for row in data['jurisdictions']}
    geometries = list(decode_geometries(topology))
    mapped = {int(props['STATE_FIPS']) for props, _ in geometries}
    if rows.keys() - mapped:
        raise ValueError(f'Jurisdictions lack map geometry: {rows.keys() - mapped}')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'text.color': '#1D2D3A'})
    fig = plt.figure(figsize=(13, 8))
    ax = fig.add_axes([.04, .20, .73, .61])
    labels = []
    for props, rings in geometries:
        row = rows.get(int(props['STATE_FIPS']))
        color = row['color'] if row else '#FFFFFF'
        vertices, codes = [], []
        for ring in rings:
            vertices.extend(ring)
            codes.extend([MplPath.MOVETO] + [MplPath.LINETO] * (len(ring) - 2) + [MplPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MplPath(vertices, codes), facecolor=color,
                               edgecolor='#64736B', linewidth=.4))
        if props['Label']:
            points = np.concatenate(rings)
            labels.append((props['Label'], points.mean(axis=0)))
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.axis('off')
    for label, center in labels:
        ax.annotate(label, center, xytext=(0, -15), textcoords='offset points',
                    ha='center', va='top', fontsize=8,
                    bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .85, 'pad': 1})
    week = data['week']
    ending = date.fromisoformat(week['weekend']).strftime('%b %d, %Y')
    fig.text(.055, .94, 'Outpatient respiratory illness activity', fontsize=24, weight='bold')
    fig.text(.055, .89, f"{data['season']} season · Week {week['weeknumber']} ending {ending}", fontsize=14)
    counts = Counter(row['category'] for row in rows.values())
    fig.text(.055, .845, 'State / jurisdiction · ' + ' · '.join(
        f'{counts[name]} {name.lower()}' for name in
        ['Very High', 'High', 'Moderate', 'Low', 'Minimal', 'Insufficient Data'] if counts[name]),
        fontsize=11, color='#596673')
    legend = fig.add_axes([.80, .23, .18, .56])
    legend.axis('off')
    legend.set_ylim(-.03, 1.08)
    legend.text(0, 1.08, 'ILI activity level', fontsize=12, weight='bold')
    for index, level in enumerate(sorted(data['levels'], key=lambda l: l['value'], reverse=True)):
        y = 1 - (index + 1) / 14
        legend.add_patch(Rectangle((0, y), .10, .045, facecolor=level['color_hexvalue'],
                                   edgecolor='#64736B', linewidth=.5))
        label = f"{level['value']:2}  {level['legend']}" if level['value'] else 'Insufficient data'
        legend.text(.15, y + .022, label, va='center', fontsize=10)
    stamp = data['retrieved_at_utc']
    retrieved = f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}'
    fig.text(.055, .145, f'Source: CDC FluView / ILINet · Retrieved {retrieved}', fontsize=10, color='#596673')
    fig.text(.055, .085, 'ILI measures visits for fever plus cough or sore throat; it is not laboratory-confirmed influenza.\n'
             'Other respiratory viruses can contribute. White indicates insufficient or unavailable data; insets are repositioned.',
             fontsize=9, color='#596673', linespacing=1.6)
    fig.text(.055, .035, data['report_url'], fontsize=9, color='#596673')
    for ext in ['png', 'svg']:
        fig.savefig(ROOT / f'plots/04_ili_activity_map.{ext}', dpi=180, facecolor='white')
    plt.close(fig)
    print('Wrote ILI activity map in PNG and SVG')


if __name__ == '__main__':
    main()
