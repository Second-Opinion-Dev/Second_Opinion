#!/usr/bin/env python3
"""Check literal origin/destination installation-key join cardinality."""
import argparse
from collections import Counter
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    root = args.output.resolve()
    if not (root / 'summary.json').is_file():
        p.error('Pipeline is incomplete')
    target = root / 'installation_join_quality.csv'
    if target.exists():
        p.error('Report already exists')
    keys = Counter()
    for path in (root / 'cleaned' / 'Installations').glob('*.csv.gz'):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        keys.update(frame['Installation'])
    observations = {'origin': Counter(), 'destination': Counter()}
    for path in (root / 'cleaned' / 'MeasurementValues').glob('*.csv.gz'):
        for frame in pd.read_csv(path, dtype=str, keep_default_na=False, usecols=['InstallationCodeOrigin', 'InstallationCodeDestination'], chunksize=100000):
            observations['origin'].update(frame['InstallationCodeOrigin'].value_counts().to_dict())
            observations['destination'].update(frame['InstallationCodeDestination'].value_counts().to_dict())
    rows = []
    for role, values in observations.items():
        for key, n in values.items():
            matches = keys[key] if key.strip() else 0
            status = 'blank' if not key.strip() else ('unmatched' if not matches else ('unique' if matches == 1 else 'would_multiply'))
            rows.append({'role': role, 'literal_key': key, 'measurement_rows': n, 'metadata_rows': matches, 'potential_inner_join_rows': n * matches, 'join_status': status})
    pd.DataFrame(rows, columns=['role', 'literal_key', 'measurement_rows', 'metadata_rows', 'potential_inner_join_rows', 'join_status']).to_csv(target, index=False)
    print('Wrote literal installation-key join report. Confirm these key relationships with TAI.')


if __name__ == '__main__':
    main()
