"""Regression checks for live map selection and validation."""
import copy
import unittest
from fetch_map import normalize


class MapDataTests(unittest.TestCase):
    def setUp(self):
        self.raw = {
            'stateinfo': [{'stateid': 1, 'statefips': '01 ', 'statename': 'Alabama'}],
            'ili_intensity': [{'iliActivityid': 0, 'value': 0, 'legend': 'Insufficient Data',
                               'color_hexvalue': '#FFFFFF'}],
            'seasons': [{'seasonid': 65, 'enabled': 1, 'label': '2025-26'},
                        {'seasonid': 66, 'enabled': 1, 'label': '2026-27'}],
            'mmwr': [{'mmwrid': 1, 'seasonid': 65, 'weekend': '2026-10-03',
                      'year': 2026, 'weeknumber': 39},
                     {'mmwrid': 2, 'seasonid': 66, 'weekend': '2026-10-10',
                      'year': 2026, 'weeknumber': 40}],
            'busdata': [{'stateid': 1, 'iliactivityid': 0, 'mmwrid': 1}]}

    def test_future_metadata_without_observations_does_not_advance_map(self):
        week, rows = normalize(self.raw)
        self.assertEqual(week['weeknumber'], 39)
        self.assertEqual(rows[0]['category'], 'Insufficient Data')

    def test_new_season_rolls_over_when_data_arrives(self):
        self.raw['busdata'].append({'stateid': 1, 'iliactivityid': 0, 'mmwrid': 2})
        week, rows = normalize(self.raw)
        self.assertEqual(week['weeknumber'], 40)
        self.assertEqual(rows[0]['season'], '2026-27')

    def test_duplicate_jurisdiction_fails(self):
        self.raw['busdata'].append(copy.deepcopy(self.raw['busdata'][0]))
        with self.assertRaises(ValueError):
            normalize(self.raw)

    def test_invalid_activity_fails(self):
        self.raw['ili_intensity'][0]['value'] = 14
        with self.assertRaises(ValueError):
            normalize(self.raw)


if __name__ == '__main__':
    unittest.main()
