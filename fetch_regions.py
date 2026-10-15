"""Download clinical-laboratory CSVs for all ten HHS regions and latest two seasons."""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fetch import BASE, log_response, validate

ROOT = Path(__file__).resolve().parent
STATE_CODES = dict(pair.split(':') for pair in (
    'Alabama:AL|Alaska:AK|Arizona:AZ|Arkansas:AR|California:CA|Colorado:CO|Connecticut:CT|'
    'Delaware:DE|District of Columbia:DC|Florida:FL|Georgia:GA|Hawaii:HI|Idaho:ID|Illinois:IL|'
    'Indiana:IN|Iowa:IA|Kansas:KS|Kentucky:KY|Louisiana:LA|Maine:ME|Maryland:MD|Massachusetts:MA|'
    'Michigan:MI|Minnesota:MN|Mississippi:MS|Missouri:MO|Montana:MT|Nebraska:NE|Nevada:NV|'
    'New Hampshire:NH|New Jersey:NJ|New Mexico:NM|New York:NY|North Carolina:NC|North Dakota:ND|'
    'Ohio:OH|Oklahoma:OK|Oregon:OR|Pennsylvania:PA|Rhode Island:RI|South Carolina:SC|'
    'South Dakota:SD|Tennessee:TN|Texas:TX|Utah:UT|Vermont:VT|Virginia:VA|Washington:WA|'
    'West Virginia:WV|Wisconsin:WI|Wyoming:WY|Puerto Rico:PR|Virgin Islands:VI|Guam:GU|'
    'American Samoa:AS|Northern Mariana Islands:MP|New York City:NY|Los Angeles:CA|Chicago:IL'
).split('|'))


def abbreviations(names):
    return sorted({STATE_CODES[name.strip()] for name in names.split(',')})


def request_payload(region_id, season_id):
    return {'AppVersion': 'Public', 'DatasourceDT': [{'ID': 0, 'Name': 'WHO_NREVSS'}],
            'RegionTypeId': 1, 'SubRegionsDT': [{'ID': region_id, 'Name': str(region_id)}],
            'SeasonsDT': [{'ID': season_id, 'Name': str(season_id)}], 'LabType': 2}


def main():
    session = requests.Session()
    session.hooks['response'].append(log_response)
    session.mount('https://', HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=['GET', 'POST'])))
    response = session.get(f'{BASE}/GetPhase02InitApp', params={'appVersion': 'Public'}, timeout=60)
    response.raise_for_status()
    metadata = response.json()
    seasons = sorted((s for s in metadata['seasons'] if s['enabled']),
                     key=lambda s: s['label'], reverse=True)[:2]
    if len(seasons) != 2:
        raise ValueError('Two seasons are required for regional charts')
    regions = sorted((r for r in metadata['hhsregion'] if r['isactive']),
                     key=lambda r: r['hhsregionnumber'])
    if [r['hhsregionnumber'] for r in regions] != list(range(1, 11)):
        raise ValueError('Expected ten distinct HHS regions')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    snapshot = ROOT / 'data/regions/snapshots' / stamp
    snapshot.mkdir(parents=True)
    (snapshot / 'metadata.json').write_text(json.dumps(metadata, indent=2))
    weeks = []
    # The chart's WHO data endpoint supplies authoritative week-ending dates,
    # including CDC's explicitly represented week 53.
    for season in seasons:
        payload = {'AppVersion': 'Public', 'SeasonID': season['seasonid'],
                   'RegionTypeID': 3, 'RegionID': 0}
        response = session.post(f'{BASE}/PostPhase02WHOGetData', json=payload, timeout=60)
        response.raise_for_status()
        calendar = response.json()['mmwr']
        weeks.extend(calendar)
        (snapshot / f"weeks_{season['label']}.json").write_text(json.dumps(calendar, indent=2))
    manifest = {'retrieved_at_utc': stamp, 'endpoint': f'{BASE}/PostPhase02StackedColumnChartDataDownload',
                'seasons': [s['label'] for s in seasons], 'weeks': weeks, 'regions': []}
    downloads = []
    for region in regions:
        number = region['hhsregionnumber']
        entry = {'number': number, 'name': region['hhsregionname'],
                 'members': region['hhsregionstates'],
                 'abbreviations': abbreviations(region['hhsregionstates']), 'downloads': []}
        for season in seasons:
            payload = request_payload(region['hhsregionid'], season['seasonid'])
            response = session.post(manifest['endpoint'], json=payload, timeout=60)
            response.raise_for_status()
            content = response.content.decode('utf-8-sig')
            rows = validate(content)
            filename = f"clinical_hhs_{number:02}_{season['label']}.csv"
            (snapshot / filename).write_text(content)
            downloads.append((filename, content))
            entry['downloads'].append({'season': season['label'], 'file': filename,
                                       'rows': len(rows), 'request': payload})
            print(f"HHS {number}, {season['label']}: {len(rows)} weeks", flush=True)
        manifest['regions'].append(entry)
    serialized = json.dumps(manifest, indent=2) + '\n'
    (snapshot / 'manifest.json').write_text(serialized)
    # Do not promote any downloads until all ten regions pass validation.
    for filename, content in downloads + [('manifest.json', serialized)]:
        path = ROOT / 'data/regions' / filename
        tmp = path.with_suffix(path.suffix + '.tmp')
        tmp.write_text(content)
        tmp.replace(path)


if __name__ == '__main__':
    main()
