#!/usr/bin/env python3
"""Stream Z-info table exports into private, traceable cleaned files and quality reports."""
import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pandas as pd

SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:  # run as a script from this folder
    sys.path.insert(0, str(SRC))
from progress_bar import Progress, duration  # noqa: E402

TABLES = ("Installations", "MeasurementPoints", "MeasurementValues")
OBSERVATIONS_TABLE = "CREATE TABLE observations(point TEXT, date TEXT, value TEXT, unit TEXT, digest TEXT)"


def process_file(table: str, raw: Path, path: Path, output: Path, chunksize: int, points: Counter,
                 installations: Counter, observations: Path | None, shard: bool) -> dict:
    """Clean one source file and return what the run needs from it.

    Everything here is local to the file, so files can be cleaned in separate processes.
    `points` and `installations` are the complete metadata keys, read only for value files.
    Value rows are written to `observations`, a new shard database when `shard` is set.
    """
    row_offset, file_stats, counts = 0, {}, Counter()
    file_points, file_installations, metadata = Counter(), Counter(), []
    database = None
    if observations is not None:
        database = sqlite3.connect(observations)
        if shard:
            database.execute(OBSERVATIONS_TABLE)
    out = output / "cleaned" / table / path.name
    for frame in pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8", encoding_errors="replace", chunksize=chunksize):
        original_columns = list(frame.columns)
        length = len(frame)
        for col in original_columns:
            stat = file_stats.setdefault(col, Counter())
            stat['blank'] += int(frame[col].str.strip().eq('').sum())
            stat['replacement'] += int(frame[col].str.contains('�', regex=False).sum())
        frame['source_file'] = str(path.relative_to(raw)).replace('\\', '/')
        frame['source_row'] = range(row_offset + 2, row_offset + length + 2)
        if table == 'Installations':
            file_installations.update(frame['Installation'])
        if table == 'MeasurementPoints':
            file_points.update(frame['MeasurementPointID'])
            metadata.append(frame)
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
    if database is not None:
        database.commit()
        database.close()
    source = str(path.relative_to(raw))
    return {
        'counts': counts,
        'points': file_points,
        'installations': file_installations,
        'metadata': pd.concat(metadata, ignore_index=True) if metadata else None,
        'inventory': {'table': table, 'source_file': source, 'rows': row_offset, 'bytes': path.stat().st_size},
        'columns': [{'table': table, 'source_file': source, 'column': col, 'blank': s['blank'], 'replacement': s['replacement']} for col, s in file_stats.items()],
        'shard': observations if shard else None,
    }


def results_in_order(jobs: list[tuple], workers: int):
    """Yield process_file results in job order; with workers > 1, up to 2 * workers files run ahead."""
    if workers == 1:
        for job in jobs:
            yield process_file(*job)
        return
    with ProcessPoolExecutor(max_workers=workers) as pool:
        pending = deque()
        for job in jobs:
            pending.append(pool.submit(process_file, *job))
            if len(pending) >= 2 * workers:
                yield pending.popleft().result()
        while pending:
            yield pending.popleft().result()


def merge_shard(database: sqlite3.Connection, shard: Path) -> None:
    """Append a worker's rows in their original order, then drop the temporary shard file."""
    database.execute('ATTACH DATABASE ? AS shard', (str(shard),))
    database.execute('INSERT INTO observations SELECT point,date,value,unit,digest FROM shard.observations ORDER BY rowid')
    database.commit()
    database.execute('DETACH DATABASE shard')
    shard.unlink()


def run(raw: Path, output: Path, limit: int | None, chunksize: int, workers: int = 1, progress: bool = False) -> None:
    if workers < 1:
        raise ValueError("Workers must be at least 1")
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
    database_path = output / "working.sqlite"
    database = sqlite3.connect(database_path)
    database.execute(OBSERVATIONS_TABLE)
    database.commit()
    points, installations = Counter(), Counter()
    inventory, columns, counts = [], [], Counter()
    point_metadata = []
    for table in TABLES:
        (output / "cleaned" / table).mkdir(parents=True, exist_ok=True)
    shards = output / "shards"
    if workers > 1:
        shards.mkdir()
    bar = Progress() if progress else None
    say = bar.message if bar else (lambda text: print(text, flush=True))
    # Progress is measured in source bytes: the value files dominate the work, and files vary in size.
    files = [path for table in TABLES for path in paths[table]]
    total_bytes, done_bytes, done_rows = sum(path.stat().st_size for path in files) or 1, 0, 0

    def clean(table_names: tuple[str, ...]) -> None:
        nonlocal done_bytes, done_rows
        # Files are absorbed in sorted order whatever finishes first, so every list, count and
        # table row ends up exactly as in a single-process run.
        jobs = []
        for table in table_names:
            for path in paths[table]:
                if table == 'MeasurementValues':
                    # The metadata is complete by now and is not changed while value files run.
                    shard = shards / f'{len(jobs):06d}.sqlite' if workers > 1 else database_path
                    jobs.append((table, raw, path, output, chunksize, points, installations, shard, workers > 1))
                else:
                    jobs.append((table, raw, path, output, chunksize, Counter(), Counter(), None, False))
        for job, result in zip(jobs, results_in_order(jobs, workers)):
            counts.update(result['counts'])
            installations.update(result['installations'])
            points.update(result['points'])
            if result['metadata'] is not None:
                point_metadata.append(result['metadata'])
            inventory.append(result['inventory'])
            columns.extend(result['columns'])
            if result['shard'] is not None:
                merge_shard(database, result['shard'])
            say(f'{job[0]}: {len(inventory)} files processed')
            if bar:
                done_bytes += result['inventory']['bytes']
                done_rows += result['inventory']['rows']
                bar.bar('Preparing', done_bytes / total_bytes,
                        f'{len(inventory)}/{len(files)} files ({job[0]}), {done_rows:,} rows')

    # Value rows are flagged against the complete metadata, so those tables run first.
    clean(TABLES[:2])
    clean(TABLES[2:])
    if workers > 1:
        shards.rmdir()
    with bar.phase('Writing point metadata and file reports') if bar else nullcontext():
        pd.DataFrame(inventory).to_csv(output / 'inventory.csv', index=False)
        pd.DataFrame(columns).to_csv(output / 'column_quality.csv', index=False)
        metadata = pd.concat(point_metadata, ignore_index=True)
        metadata['duplicate_point_id'] = metadata['MeasurementPointID'].map(points).gt(1)
        metadata.to_csv(output / 'point_metadata.csv.gz', index=False, compression='gzip')
        pd.DataFrame([{'point_id': k, 'metadata_rows': v} for k, v in points.items() if v > 1]).to_csv(output / 'duplicate_point_metadata.csv', index=False)
    say('Building cross-file quality index; this can take time and disk space.')
    with bar.phase('Building cross-file quality index and duplicate reports') if bar else nullcontext():
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
    if bar:
        bar.close(f'Prepared {len(files)} files, {done_rows:,} rows in {duration(bar.elapsed())}')
    summary = {'counts': dict(counts), 'file_limit_per_table': limit, 'pandas_version': pd.__version__, 'limitations': ['Date and unit meanings are unconfirmed.', 'Digest uses pandas 64-bit hashes: duplicate candidates need exact verification.', 'Cross-file matching uses literal point and date strings.', 'Unknown joins are flagged but not expanded; origin key mapping is unconfirmed.', 'No rows removed, imputed, converted or declared anomalous.', 'A file limit produces an incomplete sample only.']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True, help='Directory containing the three Z-info table folders')
    parser.add_argument('--output', type=Path, required=True, help='New or empty private output directory')
    parser.add_argument('--chunksize', type=int, default=100000)
    parser.add_argument('--limit-files', type=int, help='For a partial smoke test only')
    parser.add_argument('--workers', type=int, default=1, metavar='N',
                        help='Clean up to N files at once in separate processes; the output is identical to N=1')
    args = parser.parse_args()
    if args.chunksize < 1 or (args.limit_files is not None and args.limit_files < 1):
        parser.error('Chunk size and file limit must be positive')
    if args.workers < 1:
        parser.error('--workers must be at least 1')
    run(args.raw, args.output, args.limit_files, args.chunksize, args.workers, progress=True)


if __name__ == '__main__':
    main()
