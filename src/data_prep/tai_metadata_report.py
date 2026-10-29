#!/usr/bin/env python3
"""Summarize measurement-point metadata and point-join cardinality locally."""
import argparse
from pathlib import Path
import pandas as pd


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    args = p.parse_args()
    root = args.output.resolve()
    if not (root / 'summary.json').is_file():
        p.error('Pipeline output is incomplete')
    targets = [root / 'point_join_quality.csv', root / 'candidate_measurements.csv', root / 'data_dictionary.csv']
    if any(x.exists() for x in targets):
        p.error('One or more reports already exist')
    metadata = pd.read_csv(root / 'point_metadata.csv.gz', dtype=str, keep_default_na=False)
    coverage = pd.read_csv(root / 'point_coverage.csv', dtype=str, keep_default_na=False)
    sizes = metadata.groupby('MeasurementPointID', dropna=False).size().rename('metadata_rows').reset_index()
    joined = coverage.merge(sizes, how='left', left_on='point', right_on='MeasurementPointID', validate='one_to_one')
    joined['metadata_rows'] = joined['metadata_rows'].fillna(0).astype(int)
    joined['potential_join_rows'] = joined['rows'].astype('int64') * joined['metadata_rows']
    joined['join_status'] = joined['metadata_rows'].map(lambda n: 'unmatched' if n == 0 else ('unique' if n == 1 else 'would_multiply'))
    joined.drop(columns=['MeasurementPointID']).to_csv(targets[0], index=False)
    columns = ['ProductDescription', 'QuantityDescription', 'ParameterDescription', 'Unit', 'InputType']
    if all(c in metadata for c in columns):
        candidate = metadata.groupby(columns, dropna=False).size().reset_index(name='point_metadata_rows')
        candidate['exploratory_influent_volume'] = candidate['ProductDescription'].str.casefold().eq('influent') & candidate['QuantityDescription'].str.casefold().eq('volume')
        candidate.sort_values('point_metadata_rows', ascending=False).to_csv(targets[1], index=False)
    else:
        pd.DataFrame(columns=columns + ['point_metadata_rows', 'exploratory_influent_volume']).to_csv(targets[1], index=False)
    quality = pd.read_csv(root / 'column_quality.csv', dtype=str, keep_default_na=False)
    dictionary = quality[['table', 'column']].drop_duplicates().copy()
    dictionary['meaning_and_unit'] = 'TODO: confirm with the data provider'
    dictionary.to_csv(targets[2], index=False)
    print('Wrote metadata, literal point-join and provisional dictionary reports. Meanings require expert confirmation.')


if __name__ == '__main__':
    main()
