#!/usr/bin/env python3
"""Generate private point-level gap, repeated-value and unit-change reports."""
import argparse
import csv
from datetime import date
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='Completed tai_pipeline.py output directory')
    args = parser.parse_args()
    output = args.output.resolve()
    if not (output / 'summary.json').is_file():
        parser.error('Pipeline is incomplete: summary.json is missing')
    report = output / 'point_sequence_quality.csv'
    if report.exists():
        parser.error('Report already exists; preserve it before rerunning')
    db = sqlite3.connect(f'file:{(output / "working.sqlite").as_posix()}?mode=ro', uri=True)
    cursor = db.execute('SELECT point,date,value,unit FROM observations ORDER BY point,date')
    with report.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['point', 'rows', 'date_parse_failures', 'missing_calendar_days_between_observations', 'consecutive_same_value_pairs', 'consecutive_unit_changes'])
        current = None
        stats = [0, 0, 0, 0, 0]
        prior_date = prior_value = prior_unit = None
        for point, raw_date, value, unit in cursor:
            if point != current:
                if current is not None:
                    writer.writerow([current, *stats])
                current, stats = point, [0, 0, 0, 0, 0]
                prior_date = prior_value = prior_unit = None
            stats[0] += 1
            try:
                day = date.fromisoformat(raw_date[:10])
            except ValueError:
                day = None
                stats[1] += 1
            if day is not None and prior_date is not None:
                delta = (day - prior_date).days
                if delta > 1:
                    stats[2] += delta - 1
            if prior_value is not None and value == prior_value and value.strip():
                stats[3] += 1
            if prior_unit is not None and unit != prior_unit:
                stats[4] += 1
            prior_date, prior_value, prior_unit = day, value, unit
        if current is not None:
            writer.writerow([current, *stats])
    db.close()
    print('Wrote point sequence report; gaps assume no sampling frequency and are not proof of missing data.')


if __name__ == '__main__':
    main()
