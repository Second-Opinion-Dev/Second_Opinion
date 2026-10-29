from contextlib import closing
import gzip
from pathlib import Path
import sqlite3
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

    def test_workers_give_the_same_output_as_one_process(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            for name in ('Installations', 'MeasurementPoints', 'MeasurementValues'):
                (raw / name).mkdir(parents=True)
            fixtures = {
                'Installations': {'a.csv.gz': 'Installation\nplant\nplant2\n', 'b.csv.gz': 'Installation\nplant3\n'},
                # p2 is described in both files, and p1 twice in one.
                'MeasurementPoints': {'a.csv.gz': 'MeasurementPointID,Unit\np1,m3\np2,m3\np1,l\n', 'b.csv.gz': 'MeasurementPointID,Unit\np2,m3\np3,mg\n'},
                'MeasurementValues': {
                    'a.csv.gz': 'InstallationCodeOrigin,MeasurementPointID,Date,Value,Unit\n' + ''.join(
                        f'plant,p1,2024-01-{day:02d},{day},m3\n' for day in range(1, 8)) + 'plant,p1,2024-01-02,2,m3\nnowhere,p9,bad,,m3\n',
                    'b.csv.gz': 'InstallationCodeOrigin,MeasurementPointID,Date,Value,Unit\nplant2,p2,2024-02-01,-1,m3\nplant2,p2,2024-02-01,0,m3\nplant,p1,2024-01-03,99,m3\n',
                    'c.csv.gz': 'InstallationCodeOrigin,MeasurementPointID,Date,Value,Unit\nplant3,p3,01/03/2024,x,mg\nplant3,p3,2024-03-02,4,mg\n',
                    'd.csv.gz': 'InstallationCodeOrigin,MeasurementPointID,Date,Value,Unit\n',
                },
            }
            for name, files in fixtures.items():
                for file, contents in files.items():
                    with gzip.open(raw / name / file, 'wt', encoding='utf-8') as stream:
                        stream.write(contents)
            serial, parallel = root / 'serial', root / 'parallel'
            run(raw, serial, None, 3)
            run(raw, parallel, None, 3, workers=3)
            self.assertFalse((parallel / 'shards').exists())
            names = sorted(path.relative_to(serial) for path in serial.rglob('*') if path.is_file())
            self.assertEqual(names, sorted(path.relative_to(parallel) for path in parallel.rglob('*') if path.is_file()))
            self.assertIn(Path('same_date_groups.csv'), names)
            for name in names:
                if name.name == 'working.sqlite':
                    rows = []
                    for folder in ('serial', 'parallel'):
                        with closing(sqlite3.connect(root / folder / name)) as database:
                            rows.append(database.execute('SELECT * FROM observations ORDER BY rowid').fetchall())
                    self.assertEqual(rows[0], rows[1])
                    self.assertGreater(len(rows[0]), 10)
                elif ''.join(name.suffixes) == '.csv.gz':
                    # Compare the decompressed text: gzip headers carry a timestamp.
                    contents = []
                    for folder in ('serial', 'parallel'):
                        with gzip.open(root / folder / name, 'rt', encoding='utf-8') as stream:
                            contents.append(stream.read())
                    self.assertEqual(contents[0], contents[1], name)
                else:
                    self.assertEqual((serial / name).read_bytes(), (parallel / name).read_bytes(), name)

    def test_rejects_fewer_than_one_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                run(Path(directory) / 'raw', Path(directory) / 'out', None, 10, workers=0)

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
