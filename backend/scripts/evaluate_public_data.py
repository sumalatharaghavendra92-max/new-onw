"""Offline EPA rating benchmark; never replaces the application's trip model.

Run from repository root: .venv/Scripts/python backend/scripts/evaluate_public_data.py --download
"""
import argparse
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd
import requests
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

URL = 'https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip'
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / 'public_data'
NUMERIC = ['year', 'displ', 'cylinders']
CATEGORICAL = ['drive', 'trany', 'VClass', 'fuelType1', 'atvType']
FEATURES = NUMERIC + CATEGORICAL


def download(destination):
    destination.mkdir(parents=True, exist_ok=True)
    response = requests.get(URL, timeout=(10, 90))
    response.raise_for_status()
    if len(response.content) > 30_000_000:
        raise ValueError('Unexpected archive size; inspect source before proceeding')
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        info = archive.getinfo('vehicles.csv')
        if info.file_size > 100_000_000:
            raise ValueError('Unexpected CSV size')
        data = archive.read(info)
    # Explicit filename prevents archive path traversal.
    (destination / 'vehicles.csv').write_bytes(data)
    manifest = {'source_url': URL, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                'source': 'FuelEconomy.gov EPA published vehicle test ratings'}
    (destination / 'source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def prepare(frame, cutoff):
    required = FEATURES + ['id', 'comb08', 'fuelType2']
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f'Missing columns: {missing}')
    frame = frame.copy()
    for name in NUMERIC + ['comb08']:
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    frame = frame.drop_duplicates('id')
    # MPG conversion only applies to liquid fuel, never MPGe or dual-fuel records.
    frame = frame[frame.fuelType1.isin(['Regular Gasoline', 'Premium Gasoline', 'Midgrade Gasoline', 'Diesel'])
                  & frame.fuelType2.fillna('').eq('')
                  & frame.comb08.gt(0) & frame.comb08.lt(150)
                  & frame.year.between(2000, cutoff + 2)]
    for name in CATEGORICAL:
        frame[name] = frame[name].fillna('Unknown').astype(str)
    frame['target_l_per_100km'] = 235.214583 / frame.comb08
    train, test = frame[frame.year <= cutoff].copy(), frame[frame.year > cutoff].copy()
    if len(train) < 100 or len(test) < 30:
        raise ValueError('Insufficient records for temporal holdout')
    return train, test


def scores(actual, predicted):
    return {'mae_l_per_100km': round(float(mean_absolute_error(actual, predicted)), 4),
            'rmse_l_per_100km': round(float(np.sqrt(mean_squared_error(actual, predicted))), 4),
            'bias_predicted_minus_actual_l_per_100km': round(float(np.mean(predicted - actual)), 4),
            'r2': round(float(r2_score(actual, predicted)), 4) if len(actual) > 1 else None}


def evaluate(data, cutoff=2022):
    train, test = prepare(data, cutoff)
    transform = ColumnTransformer([
        ('numeric', SimpleImputer(strategy='median'), NUMERIC),
        ('categorical', OneHotEncoder(handle_unknown='ignore'), CATEGORICAL)])
    model = make_pipeline(transform, RandomForestRegressor(n_estimators=150, min_samples_leaf=3,
                                                          random_state=42, n_jobs=2))
    target = 'target_l_per_100km'
    model.fit(train[FEATURES], train[target])
    prediction = model.predict(test[FEATURES])
    baseline = np.repeat(train[target].median(), len(test))
    groups = {}
    for fuel in sorted(test.fuelType1.unique()):
        mask = test.fuelType1.eq(fuel).to_numpy()
        groups[fuel] = {'count': int(mask.sum()), **scores(test.loc[mask, target], prediction[mask])}
    # Report model families seen in training, rather than claiming unseen-vehicle generalization.
    family = lambda df: set(zip(df['make'].fillna(''), df['model'].fillna('')))
    overlap = len(family(test) & family(train)) if {'make', 'model'} <= set(data.columns) else None
    return {'benchmark': 'EPA vehicle efficiency ratings; NOT deployed route-model accuracy',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'target': 'Published combined fuel economy converted to L/100 km',
            'features': FEATURES, 'train_rows': len(train), 'test_rows': len(test),
            'train_years': [int(train.year.min()), int(train.year.max())],
            'test_years': [int(test.year.min()), int(test.year.max())],
            'split': 'Fixed model-year holdout; preprocessing fitted only on training records',
            'test_model_families_also_in_train': overlap,
            'random_forest': scores(test[target], prediction),
            'train_median_baseline': scores(test[target], baseline), 'fuel_slices': groups,
            'deployment_eligible': False,
            'limitations': ['US published test-cycle ratings, not real-time trip fuel measurements',
                           'No route, cargo, traffic, elevation, driver or Indian fleet validation',
                           'Model families may recur across years; not an unseen-family holdout',
                           'Single fixed split; no uncertainty interval or independent replication',
                           'Experimental model is not saved or installed into routing']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DIR)
    parser.add_argument('--train-through', type=int, default=2022)
    args = parser.parse_args()
    if args.download:
        download(args.data_dir)
    path = args.data_dir / 'vehicles.csv'
    report = evaluate(pd.read_csv(path, low_memory=False), args.train_through)
    report['dataset_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = args.data_dir / 'source.json'
    if manifest.exists():
        report['provenance'] = json.loads(manifest.read_text(encoding='utf-8'))
    (args.data_dir / 'evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

