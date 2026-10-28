import gzip
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from data_prep.tai_pipeline import run


class PipelineTest(unittest.TestCase):
    def test_provenance_flags_and_conflicts_survive_chunk_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            for name in ('Installations', 'MeasurementPoints', 'MeasurementValues'):
                (raw / name).mkdir(parents=True)
            fixtures = {
                'Installations': 'Installation\nplant\n',
                'MeasurementPoints': 'MeasurementPointID\np1\n',
                'MeasurementValues': 'InstallationCodeOrigin,MeasurementPointID,Date,Value,Unit\nplant,p1,2024-01-01,1,m3\nplant,p1,2024-01-01,1,m3\nplant,p1,2024-01-01,2,m3\nother,unknown,bad,nope,m3\n',
            }
            for name, contents in fixtures.items():
                with gzip.open(raw / name / 'one.csv.gz', 'wt', encoding='utf-8') as stream:
                    stream.write(contents)
            out = root / 'out'
            run(raw, out, None, 2)
            clean = pd.read_csv(out / 'cleaned/MeasurementValues/one.csv.gz')
            self.assertEqual(clean['source_row'].tolist(), [2, 3, 4, 5])
            self.assertEqual(clean['Value'].tolist(), ['1', '1', '2', 'nope'])
            self.assertTrue(clean.loc[3, 'flag_invalid_value'])
            self.assertTrue(clean.loc[3, 'flag_invalid_date'])
            self.assertTrue(clean.loc[3, 'flag_unknown_point'])
            group = pd.read_csv(out / 'same_date_groups.csv').iloc[0]
            self.assertEqual((group['rows'], group['distinct_records'], group['exact_duplicates']), (3, 2, 1))

    def test_refuses_to_overwrite_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'out'
            output.mkdir()
            (output / 'keep').write_text('original')
            with self.assertRaises(ValueError):
                run(root / 'raw', output, None, 10)
            self.assertEqual((output / 'keep').read_text(), 'original')


if __name__ == '__main__':
    unittest.main()
