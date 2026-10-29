#!/usr/bin/env python3
"""Build the dashboard's SQLite results index ahead of time, with the dashboard's own builder.

The dashboard builds the same index when it connects to a results folder whose entries are
missing or out of date. Building it here means connecting to the same folder reuses it.
The index holds measurement-derived results: keep it private and out of Git.
"""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

DASHBOARD = Path(__file__).resolve().parents[1] / 'dashboard'


def dashboard_server():
    if str(DASHBOARD) not in sys.path:
        sys.path.insert(0, str(DASHBOARD))
    import server
    return server


def is_current(results: Path, index: Path, measurements: list[str]) -> bool:
    """True when every measurement's indexed run matches its result files, as the dashboard checks."""
    server = dashboard_server()
    if not index.is_file():
        return False
    try:
        with closing(sqlite3.connect(index.resolve().as_uri() + '?mode=ro', uri=True)) as database:
            for metric in measurements:
                paths = [results / f'forest_{metric}' / 'run_info.json', results / f'history_{metric}' / 'run_info.json',
                         results / f'forest_{metric}' / 'scored_records.csv.gz']
                if not all(path.is_file() for path in paths):
                    return False
                row = database.execute('SELECT fingerprint,status FROM runs WHERE metric=?', (metric,)).fetchone()
                if row is None or row[0] != server.fingerprint(paths) or row[1] != 'provisional_unvalidated':
                    return False
    except sqlite3.Error:
        return False
    return True


def main() -> None:
    server = dashboard_server()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', type=Path, required=True, help='Pipeline results folder holding forest_<metric>/ and history_<metric>/')
    parser.add_argument('--catalog', type=Path, help='Extracted export whose Installations/ names the plants')
    parser.add_argument('--index', type=Path, default=server.DB, help='Index file (default: the one the dashboard reads)')
    parser.add_argument('--measurement', nargs='+', choices=server.METRICS, default=list(server.METRICS),
                        help='Measurements that must end up in the index')
    args = parser.parse_args()
    if args.catalog is not None and not args.catalog.is_dir():
        parser.error(f'catalog folder not found: {args.catalog}')
    server.build_index(args.results.resolve(), args.catalog.resolve() if args.catalog else None, args.index)
    state = server.state
    for error in state['errors']:
        print(f'  {error}', flush=True)
    if state['phase'] != 'ready':
        raise SystemExit(f"Index build failed: {state['message']}")
    missing = [metric for metric in args.measurement if metric not in state['metrics']]
    if missing:
        raise SystemExit(f"Not indexed: {', '.join(missing)}; see the messages above")
    print(f"Indexed {', '.join(state['metrics'])} into {args.index}: {state['processed']} readings, "
          f"{state['skipped']} skipped for missing provenance", flush=True)


if __name__ == '__main__':
    main()
