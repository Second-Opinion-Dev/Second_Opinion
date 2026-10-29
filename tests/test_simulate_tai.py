import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from data_prep.tai_pipeline import run as prepare
from history_detector.history_detector import MEASUREMENTS, select_points
from simulation import simulate_tai as sim


def build(root: Path, seed: int = 7, **overrides):
    options = dict(seed=seed, plants=4, target_rows=30000, start='2023-01-01', end='2024-06-30', log=lambda _: None)
    options.update(overrides)
    return sim.run(root, **options)


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8', encoding_errors='replace')


class SimulationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name) / 'sim'
        cls.manifest = build(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_schema_matches_the_export_tables(self):
        expected = {'Installations': sim.INSTALLATION_COLUMNS, 'MeasurementPoints': sim.POINT_COLUMNS,
                    'MeasurementValues': sim.VALUE_COLUMNS}
        for table, columns in expected.items():
            files = sorted((self.root / 'extracted' / table).glob('*.csv.gz'))
            self.assertTrue(files)
            for path in files:
                self.assertEqual(list(read_table(path).columns), columns)
        plants = {p.name for p in (self.root / 'extracted' / 'MeasurementValues').glob('*.csv.gz')}
        self.assertEqual(plants, {p.name for p in (self.root / 'extracted' / 'MeasurementPoints').glob('*.csv.gz')})
        installations = {p.name[:-7] for p in (self.root / 'extracted' / 'Installations').glob('*.csv.gz')}
        self.assertTrue(all(name.startswith('ZZ.') for name in installations))

    def test_anomalous_share_meets_the_requested_minimum(self):
        self.assertGreaterEqual(self.manifest['anomalous_share'], 0.10)
        self.assertGreaterEqual(self.manifest['value_anomaly_share'], 0.10)
        self.assertEqual(set(self.manifest['rows_by_label']) & set(sim.VALUE_ANOMALIES.values()),
                         set(sim.VALUE_ANOMALIES.values()))

    def test_row_labels_point_at_the_rows_they_describe(self):
        checked = 0
        for path in sorted((self.root / 'ground_truth' / 'row_labels').glob('*.csv.gz')):
            labels = pd.read_csv(path)
            values = read_table(self.root / 'extracted' / 'MeasurementValues' / path.name)
            self.assertLessEqual(labels['source_row'].max() - 2, len(values) - 1)
            rows = labels.assign(position=labels['source_row'] - 2).merge(
                values, left_on='position', right_index=True)
            dropout = rows[rows['anomaly_type'] == 'dropout']
            self.assertTrue((pd.to_numeric(dropout['Value']) == 0).all())
            blank = rows[rows['anomaly_type'] == 'blank_value']
            self.assertTrue((blank['Value'] == '').all())
            stuck = rows[rows['anomaly_type'] == 'stuck'].groupby('episode_id')['Value'].nunique()
            self.assertTrue((stuck == 1).all())
            negative = rows[rows['anomaly_type'] == 'negative']
            self.assertTrue((pd.to_numeric(negative['Value']) <= 0).all())
            checked += len(dropout) + len(blank) + len(stuck) + len(negative)
        self.assertGreater(checked, 0)

    def test_core_groups_select_points_and_metadata_ids_are_unique(self):
        frames = []
        for path in sorted((self.root / 'extracted' / 'MeasurementPoints').glob('*.csv.gz')):
            frame = read_table(path)
            frame['source_file'] = f'MeasurementPoints/{path.name}'
            frames.append(frame)
        metadata = pd.concat(frames, ignore_index=True)
        self.assertFalse(metadata['MeasurementPointID'].duplicated().any())
        for group in MEASUREMENTS:
            selected = select_points(metadata, group)
            self.assertFalse(selected.empty, group)
            self.assertTrue(selected['InputType'].eq('scada').all())
        tags = {k.core: k.label for k in sim.KINDS if k.core}
        oxygen = select_points(metadata, 'oxygen')
        self.assertTrue(oxygen['MeasurementObjectDescription'].str.startswith(tags['oxygen']).all())

    def test_preparation_flags_match_the_injected_faults(self):
        prepared = Path(self.directory.name) / 'prepared'
        prepare(self.root / 'extracted', prepared, None, 5000)
        counts = json.loads((prepared / 'summary.json').read_text(encoding='utf-8'))['counts']
        by_label = self.manifest['rows_by_label']
        self.assertEqual(counts['flag_blank_value'], by_label.get('blank_value', 0))
        self.assertEqual(counts['flag_invalid_value'], by_label.get('invalid_value', 0))
        self.assertEqual(counts['flag_invalid_date'], by_label.get('invalid_date', 0))
        self.assertEqual(counts['flag_unknown_point'], by_label.get('unknown_point', 0))
        self.assertEqual(counts['flag_unknown_origin'], by_label.get('unknown_origin', 0))
        self.assertEqual(counts['MeasurementValues'], self.manifest['rows'])

    def test_same_seed_reproduces_the_files_and_other_seeds_differ(self):
        with tempfile.TemporaryDirectory() as other:
            again = Path(other) / 'again'
            different = Path(other) / 'different'
            build(again)
            other_seed = build(different, seed=8)
            for path in sorted((self.root / 'extracted' / 'MeasurementValues').glob('*.csv.gz')):
                self.assertEqual(path.read_bytes(), (again / 'extracted' / 'MeasurementValues' / path.name).read_bytes())
            self.assertNotEqual(other_seed['rows_by_label'], self.manifest['rows_by_label'])

    def test_refuses_a_non_empty_output_directory(self):
        with self.assertRaises(ValueError):
            build(self.root)

    def test_anomalies_never_touch_the_first_days_of_a_series(self):
        episodes = pd.read_csv(self.root / 'ground_truth' / 'episodes.csv.gz')
        self.assertFalse(episodes.empty)
        first = {}
        for path in (self.root / 'extracted' / 'MeasurementValues').glob('*.csv.gz'):
            values = read_table(path)
            valid = values[values['Date'].str.match(r'^\d{4}-\d{2}-\d{2}$') & ~values['MeasurementPointID'].str.endswith('.UNK')]
            first.update(valid.groupby('MeasurementPointID')['Date'].min().to_dict())
        gap = [(pd.Timestamp(r.start_date) - pd.Timestamp(first[r.MeasurementPointID])).days
               for r in episodes.itertuples() if r.MeasurementPointID in first]
        self.assertGreaterEqual(min(gap), sim.PROTECTED_DAYS)


if __name__ == '__main__':
    unittest.main()
