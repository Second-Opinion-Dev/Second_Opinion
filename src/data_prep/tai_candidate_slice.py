#!/usr/bin/env python3
"""Export an unapproved exploratory Influent/Volume slice from cleaned TAI files."""
import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path, help='Completed pipeline output directory')
    args = p.parse_args()
    root = args.output.resolve()
    if not (root / 'summary.json').is_file():
        p.error('Pipeline is incomplete')
    target = root / 'exploratory_influent_volume'
    if target.exists():
        p.error('Candidate directory already exists')
    target.mkdir()
    metadata = pd.read_csv(root / 'point_metadata.csv.gz', dtype=str, keep_default_na=False)
    selected = metadata[metadata['ProductDescription'].str.casefold().eq('influent') & metadata['QuantityDescription'].str.casefold().eq('volume')].copy()
    selected.to_csv(target / 'candidate_metadata.csv.gz', index=False, compression='gzip')
    point_ids = set(selected['MeasurementPointID'])
    rows = 0
    for path in sorted((root / 'cleaned' / 'MeasurementValues').glob('*.csv.gz')):
        written = 0
        for frame in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=100000):
            subset = frame[frame['MeasurementPointID'].isin(point_ids)]
            if len(subset):
                subset.to_csv(target / path.name, mode='wt' if not written else 'at', header=not written, index=False, compression='gzip')
                written += len(subset)
        rows += written
    (target / 'README.txt').write_text('Exploratory metadata filter only. Measurement meaning, compatible units, plant peers and selection are not confirmed. Preserve source columns and do not treat this as an approved modelling slice.\n', encoding='utf-8')
    print(f'Exploratory candidate metadata rows: {len(selected)}; measurement rows: {rows}. Not expert-approved.')


if __name__ == '__main__':
    main()
