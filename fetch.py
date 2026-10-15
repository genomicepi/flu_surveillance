"""Download national CDC clinical-laboratory data; preserve each retrieval."""
import argparse
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://gis.cdc.gov/flu2"
ROOT = Path(__file__).resolve().parent
COLUMNS = ["YEAR", "WEEK", "TOTAL SPECIMENS", "TOTAL A", "TOTAL B",
           "PERCENT POSITIVE", "PERCENT A", "PERCENT B"]


def validate(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if reader.fieldnames != COLUMNS:
        raise ValueError(f"CDC CSV schema changed: {reader.fieldnames}")
    rows = list(reader)
    if not rows:
        raise ValueError("CDC returned no observations")
    keys = set()
    for row in rows:
        key = (int(row["YEAR"]), int(row["WEEK"]))
        if key in keys or not 1 <= key[1] <= 53:
            raise ValueError(f"Duplicate or invalid week: {key}")
        keys.add(key)
        # Preserve missing observations, rather than interpreting them as zero.
        for col in COLUMNS[2:]:
            if row[col].strip().upper() in {"", "NA", "N/A", "X", "NULL"}:
                continue
            value = float(row[col])
            if value < 0 or (col.startswith("PERCENT") and value > 100):
                raise ValueError(f"Invalid {col}: {value}")
        vals = [row[c] for c in COLUMNS[2:5]]
        try:
            total, a, b = map(float, vals)
        except ValueError:
            continue
        if a + b > total:
            raise ValueError(f"Positive counts exceed specimens: {key}")
    return rows


def log_response(response, *args, **kwargs):
    print(f"CDC HTTP {response.status_code} | {response.request.method} {response.url}", flush=True)
    if response.status_code >= 400:
        print(f"CDC error content-type: {response.headers.get('Content-Type', 'unknown')}", flush=True)
        print(f"CDC error body (first 1000 characters): {response.text[:1000]}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seasons", nargs="+", help="Example: 2025-26 2024-25; default: latest two")
    args = parser.parse_args()
    session = requests.Session()
    session.hooks["response"].append(log_response)
    session.mount("https://", HTTPAdapter(max_retries=Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"])))
    init = session.get(f"{BASE}/GetPhase02InitApp", params={"appVersion": "Public"}, timeout=60)
    init.raise_for_status()
    seasons = init.json()["seasons"]
    available = {s["label"]: s for s in seasons if s["enabled"]}
    labels = args.seasons or sorted(available, reverse=True)[:2]
    unknown = set(labels) - available.keys()
    if unknown:
        raise ValueError(f"Unknown seasons: {sorted(unknown)}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    data = ROOT / "data"
    snapshot = data / "snapshots" / stamp
    snapshot.mkdir(parents=True)
    (snapshot / "metadata.json").write_text(json.dumps(init.json(), indent=2))
    manifest = {"retrieved_at_utc": stamp, "endpoint": f"{BASE}/PostPhase02StackedColumnChartDataDownload",
                "geography": "National", "laboratories": "Clinical", "seasons": []}
    downloads = []
    for label in labels:
        sid = available[label]["seasonid"]
        payload = {"AppVersion": "Public", "DatasourceDT": [{"ID": 0, "Name": "WHO_NREVSS"}],
                   "RegionTypeId": 3, "SubRegionsDT": [{"ID": 0, "Name": ""}],
                   "SeasonsDT": [{"ID": sid, "Name": str(sid)}], "LabType": 2}
        response = session.post(manifest["endpoint"], json=payload, timeout=60)
        response.raise_for_status()
        text = response.content.decode("utf-8-sig")
        rows = validate(text)
        name = f"clinical_national_{label}.csv"
        (snapshot / name).write_text(text)
        downloads.append((name, text))
        manifest["seasons"].append({"label": label, "rows": len(rows), "request": payload,
                                     "last_observation": max((int(r["YEAR"]), int(r["WEEK"])) for r in rows)})
        print(f"{label}: {len(rows)} weeks")
    # Promote only after every requested season has passed validation.
    for name, text in downloads:
        temporary = data / (name + ".tmp")
        temporary.write_text(text)
        temporary.replace(data / name)
    serialized = json.dumps(manifest, indent=2)
    (snapshot / "manifest.json").write_text(serialized)
    (data / "manifest.json").write_text(serialized)
    print(f"Saved CSVs to {data}; archived retrieval {stamp}")


if __name__ == "__main__":
    main()
