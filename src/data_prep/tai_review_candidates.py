#!/usr/bin/env python3
"""Copy parsing and missing-value review candidates without removing retained rows."""
import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path, help='Completed pipeline output directory')
    args = p.parse_args()
    root = args.output.resolve()
    if not (root / 'summary.json').is_file():
        p.error('Pipeline output is incomplete')
    target = root / 'review_candidates'
    if target.exists():
        p.error('Review candidate directory already exists')
    target.mkdir()
    count = 0
    for source in sorted((root / 'cleaned' / 'MeasurementValues').glob('*.csv.gz')):
        written = 0
        for frame in pd.read_csv(source, dtype=str, keep_default_na=False, chunksize=100000):
            flags = ['flag_blank_value', 'flag_invalid_value', 'flag_invalid_date', 'flag_unknown_point']
            mask = frame[flags].apply(lambda col: col.str.lower().eq('true')).any(axis=1)
            rows = frame[mask]
            if len(rows):
                rows.to_csv(target / source.name, mode='wt' if not written else 'at', header=not written, index=False, compression='gzip')
                written += len(rows)
        count += written
    (target / 'README.txt').write_text('Review candidates are copies, not exclusions. Rows remain in cleaned outputs. Flags are not confirmed data errors. Duplicate and origin-join candidates are reported separately.\n', encoding='utf-8')
    print(f'Copied {count} review candidate rows; no rows excluded.')


if __name__ == '__main__':
    main()
