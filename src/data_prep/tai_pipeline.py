#!/usr/bin/env python3
"""Stream Z-info table exports into private, traceable cleaned files and quality reports."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

TABLES = ("Installations", "MeasurementPoints", "MeasurementValues")


def run(raw: Path, output: Path, limit: int | None, chunksize: int) -> None:
    raw, output = raw.resolve(), output.resolve()
    if raw == output or raw in output.parents or output in raw.parents:
        raise ValueError("Raw and output locations must be separate")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; select a new directory")
    output.mkdir(parents=True, exist_ok=True)
    paths = {t: sorted((raw / t).glob("*.csv.gz")) for t in TABLES}
    if any(not p for p in paths.values()):
        raise ValueError("Expected nonempty Installations, MeasurementPoints and MeasurementValues folders")
    if limit:
        paths = {k: v[:limit] for k, v in paths.items()}
    database = sqlite3.connect(output / "working.sqlite")
    database.execute("CREATE TABLE observations(point TEXT, date TEXT, value TEXT, unit TEXT, digest TEXT)")
    points, installations = Counter(), Counter()
    inventory, columns, counts = [], [], Counter()
    point_metadata = []
    for table in TABLES:
        (output / "cleaned" / table).mkdir(parents=True, exist_ok=True)
        for path in paths[table]:
            row_offset, file_stats = 0, {}
            out = output / "cleaned" / table / path.name
            for frame in pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8", encoding_errors="replace", chunksize=chunksize):
                original_columns = list(frame.columns)
                length = len(frame)
                for col in original_columns:
                    stat = file_stats.setdefault(col, Counter())
                    stat['blank'] += int(frame[col].str.strip().eq('').sum())
                    stat['replacement'] += int(frame[col].str.contains('\ufffd', regex=False).sum())
                frame['source_file'] = str(path.relative_to(raw)).replace('\\', '/')
                frame['source_row'] = range(row_offset + 2, row_offset + length + 2)
                if table == 'Installations':
                    installations.update(frame['Installation'])
                if table == 'MeasurementPoints':
                    points.update(frame['MeasurementPointID'])
                    point_metadata.append(frame)
                if table == 'MeasurementValues':
                    date = pd.to_datetime(frame['Date'], errors='coerce', format='mixed')
                    value = pd.to_numeric(frame['Value'], errors='coerce')
                    frame['parsed_date'] = date.dt.strftime('%Y-%m-%dT%H:%M:%S').fillna('')
                    frame['parsed_value'] = value
                    frame['flag_blank_value'] = frame['Value'].str.strip().eq('')
                    frame['flag_invalid_value'] = ~frame['flag_blank_value'] & value.isna()
                    frame['flag_invalid_date'] = date.isna()
                    frame['flag_unknown_point'] = ~frame['MeasurementPointID'].isin(points)
                    frame['flag_unknown_origin'] = ~frame['InstallationCodeOrigin'].isin(installations)
                    for col in ('flag_blank_value', 'flag_invalid_value', 'flag_invalid_date', 'flag_unknown_point', 'flag_unknown_origin'):
                        counts[col] += int(frame[col].sum())
                    counts['negative'] += int(value.lt(0).sum())
                    counts['zero'] += int(value.eq(0).sum())
                    # Digest all source fields to distinguish exact records from same-date conflicts.
                    hashes = pd.util.hash_pandas_object(frame[original_columns], index=False).astype(str)
                    database.executemany('INSERT INTO observations VALUES (?,?,?,?,?)', zip(frame['MeasurementPointID'], frame['Date'], frame['Value'], frame['Unit'], hashes))
                frame.to_csv(out, mode='wt' if row_offset == 0 else 'at', index=False, header=row_offset == 0, compression='gzip')
                row_offset += length
            counts[table] += row_offset
            inventory.append({'table': table, 'source_file': str(path.relative_to(raw)), 'rows': row_offset, 'bytes': path.stat().st_size})
            columns.extend({'table': table, 'source_file': str(path.relative_to(raw)), 'column': col, 'blank': s['blank'], 'replacement': s['replacement']} for col, s in file_stats.items())
            database.commit()
            print(f'{table}: {len(inventory)} files processed', flush=True)
    pd.DataFrame(inventory).to_csv(output / 'inventory.csv', index=False)
    pd.DataFrame(columns).to_csv(output / 'column_quality.csv', index=False)
    metadata = pd.concat(point_metadata, ignore_index=True)
    metadata['duplicate_point_id'] = metadata['MeasurementPointID'].map(points).gt(1)
    metadata.to_csv(output / 'point_metadata.csv.gz', index=False, compression='gzip')
    pd.DataFrame([{'point_id': k, 'metadata_rows': v} for k, v in points.items() if v > 1]).to_csv(output / 'duplicate_point_metadata.csv', index=False)
    print('Building cross-file quality index; this can take time and disk space.', flush=True)
    database.execute('CREATE INDEX observation_key ON observations(point,date)')
    database.commit()
    queries = {
        'same_date_groups.csv': "SELECT point,date,COUNT(*) AS rows,COUNT(DISTINCT digest) AS distinct_records,COUNT(*)-COUNT(DISTINCT digest) AS exact_duplicates FROM observations GROUP BY point,date HAVING COUNT(*)>1",
        'point_coverage.csv': "SELECT point,COUNT(*) AS rows,MIN(date) AS first_date,MAX(date) AS last_date,COUNT(DISTINCT date) AS distinct_dates,COUNT(DISTINCT unit) AS distinct_units,COUNT(DISTINCT value) AS distinct_values FROM observations GROUP BY point",
    }
    for name, query in queries.items():
        import csv
        cursor = database.execute(query)
        with (output / name).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow([d[0] for d in cursor.description])
            while batch := cursor.fetchmany(10000):
                writer.writerows(batch)
    database.close()
    summary = {'counts': dict(counts), 'file_limit_per_table': limit, 'pandas_version': pd.__version__, 'limitations': ['Date and unit meanings are unconfirmed.', 'Digest uses pandas 64-bit hashes: duplicate candidates need exact verification.', 'Cross-file matching uses literal point and date strings.', 'Unknown joins are flagged but not expanded; origin key mapping is unconfirmed.', 'No rows removed, imputed, converted or declared anomalous.', 'A file limit produces an incomplete sample only.']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True, help='Directory containing the three Z-info table folders')
    parser.add_argument('--output', type=Path, required=True, help='New or empty private output directory')
    parser.add_argument('--chunksize', type=int, default=100000)
    parser.add_argument('--limit-files', type=int, help='For a partial smoke test only')
    args = parser.parse_args()
    if args.chunksize < 1 or (args.limit_files is not None and args.limit_files < 1):
        parser.error('Chunk size and file limit must be positive')
    run(args.raw, args.output, args.limit_files, args.chunksize)


if __name__ == '__main__':
    main()
