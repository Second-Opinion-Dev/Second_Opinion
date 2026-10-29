#!/usr/bin/env python3
"""Verify retained row counts and provenance against the pipeline inventory."""
import argparse
from pathlib import Path
import sys

import pandas as pd

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:  # run as a script from this folder
    sys.path.insert(0, str(SRC))
from progress_bar import Progress, duration  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    if not (root / 'summary.json').is_file():
        parser.error('Pipeline is incomplete')
    inv = pd.read_csv(root / 'inventory.csv', keep_default_na=False)
    errors = []
    total = 0
    # The inventory gives every file's row count, so progress is measured in rows checked.
    expected_rows, progress = max(int(inv['rows'].sum()), 1), Progress()
    for number, record in enumerate(inv.itertuples(index=False), 1):
        path = root / 'cleaned' / record.source_file
        count, next_row = 0, 2
        if path.exists():
            for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, usecols=['source_file', 'source_row'], chunksize=100000):
                rows = pd.to_numeric(chunk['source_row'], errors='coerce')
                expected = pd.Series(range(next_row, next_row + len(chunk)), index=chunk.index)
                if not chunk['source_file'].eq(record.source_file.replace('\\', '/')).all() or not rows.eq(expected).all():
                    errors.append(f'{record.source_file}: provenance mismatch')
                count += len(chunk)
                next_row += len(chunk)
                progress.bar('Verifying', (total + count) / expected_rows,
                             f'{number}/{len(inv)} files, {total + count:,}/{expected_rows:,} rows')
        if count != int(record.rows):
            errors.append(f'{record.source_file}: row count mismatch')
        total += count
    progress.close(f'Checked {len(inv)} files, {total:,} rows in {duration(progress.elapsed())}')
    if errors:
        raise SystemExit(f'Verification failed for {len(errors)} checks; details stay local. First: {errors[0]}')
    print(f'Verified {len(inv)} files and {total} retained rows with sequential source record provenance.')


if __name__ == '__main__':
    main()
