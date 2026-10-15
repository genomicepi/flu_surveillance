"""Regression checks for regional requests, titles, and chronological plotting."""
import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fetch import COLUMNS
from fetch_regions import abbreviations, request_payload
from plot_regions import regional_rows


class RegionTests(unittest.TestCase):
    def test_city_reporting_areas_use_parent_state(self):
        self.assertEqual(abbreviations('New Jersey, New York, New York City, Puerto Rico, Virgin Islands'),
                         ['NJ', 'NY', 'PR', 'VI'])
        self.assertEqual(abbreviations('California, Los Angeles, Guam'), ['CA', 'GU'])

    def test_region_request_is_not_national(self):
        request = request_payload(2, 65)
        self.assertEqual(request['RegionTypeId'], 1)
        self.assertEqual(request['SubRegionsDT'], [{'ID': 2, 'Name': '2'}])
        self.assertEqual(request['LabType'], 2)

    def test_dates_follow_cdc_and_preserve_missing_week(self):
        weeks = [{'year': 2024, 'weeknumber': 21, 'weekend': '2024-05-25'},
                 {'year': 2024, 'weeknumber': 52, 'weekend': '2024-12-28'},
                 {'year': 2025, 'weeknumber': 1, 'weekend': '2025-01-04'},
                 {'year': 2025, 'weeknumber': 3, 'weekend': '2025-01-18'}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data/regions').mkdir(parents=True)
            with (root / 'data/regions/test.csv').open('w') as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
                for week in weeks:
                    writer.writerow(dict(zip(COLUMNS, [week['year'], week['weeknumber'], 100, 10, 5, 15, 10, 5])))
            with patch('plot_regions.ROOT', root):
                dates, values = regional_rows({'downloads': [{'file': 'test.csv'}]},
                                               {'seasons': ['2024-25', '2023-24'], 'weeks': weeks})
        self.assertEqual((dates[dates.index(date(2025, 1, 4))] - date(2024, 12, 28)).days, 7)
        self.assertEqual(values['PERCENT POSITIVE'][dates.index(date(2025, 1, 4))], 15)
        self.assertTrue(np.isnan(values['PERCENT POSITIVE'][dates.index(date(2025, 1, 11))]))


if __name__ == '__main__':
    unittest.main()
