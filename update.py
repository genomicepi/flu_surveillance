"""Fetch the latest enabled CDC seasons and render that exact season pair."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    subprocess.run([sys.executable, '-u', str(ROOT / 'fetch.py')], check=True)
    manifest = json.loads((ROOT / 'data/manifest.json').read_text())
    seasons = sorted((item['label'] for item in manifest['seasons']), reverse=True)
    if len(seasons) < 2:
        raise ValueError('At least two downloaded seasons are required for comparison')
    subprocess.run([sys.executable, str(ROOT / 'plot.py'),
                    '--current', seasons[0], '--previous', seasons[1]], check=True)


if __name__ == '__main__':
    main()
