"""Fetch the latest published state/jurisdiction ILI activity from CDC's live widget."""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fetch import log_response

ROOT = Path(__file__).resolve().parent
ENDPOINT = 'https://gis.cdc.gov/FluView1/Phase1IniP'


def normalize(raw):
    states = {s['stateid']: s for s in raw['stateinfo']}
    levels = {s['iliActivityid']: s for s in raw['ili_intensity']}
    weeks = {w['mmwrid']: w for w in raw['mmwr']}
    seasons = {s['seasonid']: s for s in raw['seasons'] if s['enabled']}
    available = {r['mmwrid'] for r in raw['busdata']
                 if weeks[r['mmwrid']]['seasonid'] in seasons}
    if not available:
        raise ValueError('CDC returned no published ILI activity weeks')
    latest = max(available, key=lambda key: weeks[key]['weekend'])
    week = weeks[latest]
    rows, seen = [], set()
    for row in raw['busdata']:
        if row['mmwrid'] != latest:
            continue
        state, level = states[row['stateid']], levels[row['iliactivityid']]
        fips = int(state['statefips'])
        if fips in seen or not 0 <= int(level['value']) <= 13:
            raise ValueError('Duplicate jurisdiction or invalid activity level')
        seen.add(fips)
        rows.append({'fips': fips, 'jurisdiction': state['statename'],
                     'level': int(level['value']), 'category': level['legend'],
                     'color': level['color_hexvalue'], 'week': week['weeknumber'],
                     'year': week['year'], 'week_ending': week['weekend'],
                     'season': seasons[week['seasonid']]['label']})
    return week, sorted(rows, key=lambda r: r['jurisdiction'])


def main():
    session = requests.Session()
    session.hooks['response'].append(log_response)
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    response = session.get(ENDPOINT, timeout=60)
    response.raise_for_status()
    raw = response.json()
    if isinstance(raw, str):
        raw = json.loads(raw)
    week, rows = normalize(raw)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report = f"https://www.cdc.gov/fluview/surveillance/{week['year']}-week-{week['weeknumber']}.html"
    result = {'retrieved_at_utc': stamp, 'endpoint': ENDPOINT,
              'report_url': report, 'week': week, 'season': rows[0]['season'],
              'levels': raw['ili_intensity'], 'jurisdictions': rows}
    snapshot = ROOT / 'data' / 'ili_snapshots' / stamp
    snapshot.mkdir(parents=True)
    (snapshot / 'raw.json').write_text(json.dumps(raw, indent=2))
    text = json.dumps(result, indent=2) + '\n'
    (snapshot / 'ili_latest.json').write_text(text)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (snapshot / 'ili_latest.csv').write_text(buf.getvalue())
    for name, content in [('ili_latest.json', text), ('ili_latest.csv', buf.getvalue())]:
        target = ROOT / 'data' / name
        temporary = target.with_suffix(target.suffix + '.tmp')
        temporary.write_text(content)
        temporary.replace(target)
    print(f"ILI map: {len(rows)} jurisdictions; {result['season']} week {week['weeknumber']}, ending {week['weekend']}")


if __name__ == '__main__':
    main()
