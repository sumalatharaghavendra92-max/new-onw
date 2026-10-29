"""Real-world check of the physics fuel model on the Vehicle Energy Dataset (VED).

VED: Oh, LeBlanc, Peng (2022), IEEE Trans. ITS, doi:10.1109/TITS.2020.3035596,
Apache-2.0, https://github.com/gsoh/VED. 383 vehicles in Ann Arbor, Michigan,
OBD-II logs Nov 2017 - Nov 2018. Ground-truth fuel comes from the mass air flow
sensor (MAF) and fuel trims, the standard VED method; it is not a fuel meter.

Nothing here tunes the physics model. The only learned parts are the per-vehicle
calibration (same rule as app/services/calibration.py) and the baselines, all
fitted on earlier trips / other vehicles than the ones they are scored on.

Run from backend/:  python scripts/validate_ved.py --download
Re-run offline:     python scripts/validate_ved.py
"""
import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.ml import physics  # noqa: E402
from app.services.calibration import PRIOR_TRIPS, RATIO_RANGE, factor_and_uncertainty  # noqa: E402

DATA_DIR = ROOT / 'public_data' / 'ved'
OUTPUT = ROOT / 'public_data' / 'ved_evaluation.json'
BASE_URL = 'https://github.com/gsoh/VED/raw/master/Data/'
FILES = ['VED_DynamicData_Part1.7z', 'VED_DynamicData_Part2.7z',
         'VED_Static_Data_ICE&HEV.xlsx', 'VED_Static_Data_PHEV&EV.xlsx']
ELEVATION_URL = 'https://api.open-meteo.com/v1/elevation'

SEED = 42
MAX_GAP_S = 5.0                 # longer gaps between samples are not integrated
STOICH_AFR = 14.7               # gasoline air-fuel ratio
GASOLINE_G_PER_L = 745.0
DRIVER_KG = 80.0
PIECE_M = 200.0                 # planning-style segment length
MAX_SEGMENTS = 99               # same cap as app/services/routing.py
TURN_DEG = 45.0
CALIBRATION_SHARE = 0.3         # each vehicle's first 30% of trips (chronological)
HOLDOUT_VEHICLE_SHARE = 0.3

COLUMNS = {'DayNum': 'day', 'VehId': 'vehicle', 'Trip': 'trip', 'Timestamp(ms)': 'ms',
           'Latitude[deg]': 'lat', 'Longitude[deg]': 'lng', 'Vehicle Speed[km/h]': 'speed_kmh',
           'MAF[g/sec]': 'maf', 'OAT[DegC]': 'oat',
           'Short Term Fuel Trim Bank 1[%]': 'stft1', 'Short Term Fuel Trim Bank 2[%]': 'stft2',
           'Long Term Fuel Trim Bank 1[%]': 'ltft1', 'Long Term Fuel Trim Bank 2[%]': 'ltft2'}


# ---------------------------------------------------------------- data download

def download(destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'source': 'Vehicle Energy Dataset (VED), Oh, LeBlanc & Peng 2022, Apache-2.0',
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'files': []}
    for name in FILES:
        response = requests.get(BASE_URL + requests.utils.quote(name), timeout=(10, 300))
        response.raise_for_status()
        if len(response.content) > 150_000_000:
            raise ValueError(f'Unexpected size for {name}; inspect before proceeding')
        (destination / name).write_bytes(response.content)
        manifest['files'].append({'name': name, 'url': BASE_URL + requests.utils.quote(name),
                                  'sha256': hashlib.sha256(response.content).hexdigest(),
                                  'bytes': len(response.content)})
    import py7zr
    out = destination / 'dynamic'
    out.mkdir(exist_ok=True)
    for name in FILES[:2]:
        with py7zr.SevenZipFile(destination / name) as archive:
            if any(n.startswith('/') or '..' in n for n in archive.getnames()):
                raise ValueError('Unsafe path in archive')
            archive.extractall(out)
    (destination / 'source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def manifest(destination):
    path = destination / 'source.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    files = [{'name': n, 'url': BASE_URL + requests.utils.quote(n),
              'sha256': hashlib.sha256((destination / n).read_bytes()).hexdigest()} for n in FILES]
    return {'source': 'Vehicle Energy Dataset (VED)', 'retrieved_at': None, 'files': files}


# ---------------------------------------------------------------- ground truth

def fuel_litres_per_second(maf, stft, ltft):
    """MAF [g/s] with fuel trims -> gasoline [L/s]. Missing trims count as 0 %."""
    trim = 1 + (np.nan_to_num(stft) + np.nan_to_num(ltft)) / 100
    return maf * trim / STOICH_AFR / GASOLINE_G_PER_L


def integrate_trip(frame):
    """Trip totals from one trip's samples. Intervals longer than MAX_GAP_S or with
    duplicate timestamps are dropped; fuel over MAF-missing intervals is imputed at
    the trip's own measured rate (coverage is reported and filtered at 90 %)."""
    frame = frame.sort_values('ms').drop_duplicates('ms')
    t = frame['ms'].to_numpy() / 1000.0
    speed = frame['speed_kmh'].to_numpy() / 3.6
    maf = frame['maf'].to_numpy()
    stft = frame[['stft1', 'stft2']].mean(axis=1).to_numpy()   # average of available banks
    ltft = frame[['ltft1', 'ltft2']].mean(axis=1).to_numpy()
    if len(t) < 2:
        return None
    dt = np.diff(t)
    moving = (dt > 0) & (dt <= MAX_GAP_S) & ~np.isnan(speed[:-1])
    with_fuel = moving & ~np.isnan(maf[:-1])
    drive_time = float(dt[moving].sum())
    fuel_time = float(dt[with_fuel].sum())
    rate = fuel_litres_per_second(maf[:-1], stft[:-1], ltft[:-1])
    measured = float(np.nansum(rate[with_fuel] * dt[with_fuel]))
    step_m = np.where(moving, speed[:-1] * dt, 0.0)
    return {
        'duration_s': drive_time,
        'distance_m': float(step_m.sum()),
        'coverage': fuel_time / drive_time if drive_time > 0 else 0.0,
        'fuel_l': measured * drive_time / fuel_time if fuel_time > 0 else float('nan'),
        't': t, 'dt': dt, 'moving': moving, 'step_m': step_m, 'speed': speed,
        'lat': frame['lat'].to_numpy(), 'lng': frame['lng'].to_numpy(),
        'temp_c': float(np.nanmean(frame['oat'])) if frame['oat'].notna().any() else float('nan'),
    }


def filter_reason(trip):
    """Why a trip is excluded, or None if it is kept."""
    if trip is None or trip['duration_s'] <= 0:
        return 'no_valid_samples'
    if trip['distance_m'] < 2000:
        return 'shorter_than_2km'
    if trip['duration_s'] < 180:
        return 'shorter_than_3min'
    if trip['coverage'] < 0.9:
        return 'maf_coverage_below_90pct'
    per_100km = trip['fuel_l'] / trip['distance_m'] * 100_000
    if not 2 <= per_100km <= 40:
        return 'implausible_l_per_100km'
    if np.isnan(trip['lat']).mean() > 0.1:
        return 'gps_missing'
    return None


# ---------------------------------------------------------------- planning-style route

def bearing(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y))


def planning_pieces(trip):
    """~200 m pieces along the driven path with each piece's elapsed driving time.

    Within-piece accelerations and stop-and-go are smoothed away, like a router's
    per-road typical speed; turns come from heading changes between pieces."""
    cum_m = np.concatenate([[0.0], np.cumsum(trip['step_m'])])
    cum_t = np.concatenate([[0.0], np.cumsum(np.where(trip['moving'], trip['dt'], 0.0))])
    lat = pd.Series(trip['lat']).interpolate(limit_direction='both').to_numpy()
    lng = pd.Series(trip['lng']).interpolate(limit_direction='both').to_numpy()
    marks = np.searchsorted(cum_m, np.arange(0, cum_m[-1], PIECE_M))
    marks = np.unique(np.append(marks, len(cum_m) - 1))
    points = [(round(float(lat[i]), 5), round(float(lng[i]), 5)) for i in marks]
    pieces = [{'distance_m': float(cum_m[b] - cum_m[a]), 'duration_s': float(cum_t[b] - cum_t[a]),
               'start': points[k], 'end': points[k + 1]} for k, (a, b) in enumerate(zip(marks, marks[1:]))]
    pieces = [p for p in pieces if p['distance_m'] > 0]
    headings = [bearing(p['start'], p['end']) for p in pieces if p['start'] != p['end']]
    turns = sum(1 for h1, h2 in zip(headings, headings[1:]) if abs((h2 - h1 + 180) % 360 - 180) > TURN_DEG)
    if len(pieces) > MAX_SEGMENTS:
        groups = np.array_split(np.arange(len(pieces)), MAX_SEGMENTS)
        pieces = [{'distance_m': sum(pieces[i]['distance_m'] for i in g),
                   'duration_s': sum(pieces[i]['duration_s'] for i in g),
                   'start': pieces[g[0]]['start'], 'end': pieces[g[-1]]['end']} for g in groups]
    return pieces, turns


def cell(point):
    return round(point[0], 3), round(point[1], 3)  # ~110 m grid; Copernicus DEM is 90 m


def fetch_elevations(cells, cache_path):
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    missing = [c for c in cells if f'{c[0]},{c[1]}' not in cache]
    failed = 0
    for start in range(0, len(missing), 100):
        chunk = missing[start:start + 100]
        for attempt in range(3):
            try:
                response = requests.get(ELEVATION_URL, params={
                    'latitude': ','.join(str(c[0]) for c in chunk),
                    'longitude': ','.join(str(c[1]) for c in chunk)}, timeout=(5, 20))
                response.raise_for_status()
                for c, h in zip(chunk, response.json()['elevation']):
                    cache[f'{c[0]},{c[1]}'] = h
                break
            except (requests.RequestException, KeyError, ValueError):
                time.sleep(2 * (attempt + 1))
        else:
            failed += len(chunk)
        time.sleep(0.25)  # stay well inside the free-tier rate
        if start % 2000 == 0:
            cache_path.write_text(json.dumps(cache))
    cache_path.write_text(json.dumps(cache))
    return cache, failed


def with_elevation(pieces, heights):
    ends = [cell(pieces[0]['start'])] + [cell(p['end']) for p in pieces]
    values = [heights.get(f'{c[0]},{c[1]}') for c in ends]
    if any(v is None for v in values):
        return [dict(p, rise_m=0.0, elevation_m=0.0) for p in pieces], False
    return [dict(p, rise_m=values[i + 1] - values[i], elevation_m=(values[i + 1] + values[i]) / 2)
            for i, p in enumerate(pieces)], True


# ---------------------------------------------------------------- predictions

def payload_for(mass_kg):
    return max(0.0, mass_kg + DRIVER_KG - physics.PROFILES['car']['curb_kg'])


def predict_planning(trip, mass_kg):
    return physics.estimate(trip['segments'], 'car', 'petrol', payload_for(mass_kg),
                            temp_c=trip['temp_c'], turns=trip['turns'])['fuel']


def predict_post_trip(trip, mass_kg):
    """Same physics on the real speed trace: every sampled interval is a segment
    (idle intervals get 1 cm so their time still counts for accessories), and the
    turn term is replaced by the measured positive kinetic-energy gains."""
    moving, dt, speed = trip['moving'], trip['dt'], trip['speed']
    cum = np.concatenate([[0.0], np.cumsum(trip['step_m'])])
    piece_cum = np.concatenate([[0.0], np.cumsum([p['distance_m'] for p in trip['segments']])])
    piece_h = [trip['segments'][0]['elevation_m'] - trip['segments'][0]['rise_m'] / 2] + \
              [p['elevation_m'] + p['rise_m'] / 2 for p in trip['segments']]
    height = np.interp(cum, piece_cum * (cum[-1] / piece_cum[-1]), piece_h)
    idx = np.flatnonzero(moving)
    segments = [{'distance_m': max(trip['step_m'][i], 0.01), 'duration_s': dt[i],
                 'rise_m': height[i + 1] - height[i], 'elevation_m': height[i]} for i in idx]
    mass = physics.PROFILES['car']['curb_kg'] + payload_for(mass_kg)
    v = np.nan_to_num(speed)
    gains = 0.5 * mass * (v[idx + 1] ** 2 - v[idx] ** 2)
    kinetic_l = gains[gains > 0].sum() / physics.POWERTRAINS['petrol']['drive'] / 1e6 / physics.FUELS['petrol']['mj_per_unit']
    base = physics.estimate(segments, 'car', 'petrol', payload_for(mass_kg), temp_c=trip['temp_c'])['fuel']
    return base + float(kinetic_l)


# ---------------------------------------------------------------- splits & metrics

def chronological_split(trips, share=CALIBRATION_SHARE):
    """Per vehicle: earliest `share` of trips for learning, the rest for scoring."""
    learn, score = [], []
    for _, group in trips.sort_values(['day', 'start_ms']).groupby('vehicle', sort=False):
        cut = int(math.floor(len(group) * share))
        learn.append(group.iloc[:cut])
        score.append(group.iloc[cut:])
    return pd.concat(learn), pd.concat(score)


def calibration_factor(ratios):
    """Exactly the app's rule: gate implausible ratios, then shrinkage towards 1."""
    kept = [r for r in ratios if RATIO_RANGE[0] <= r <= RATIO_RANGE[1]]
    state = SimpleNamespace(trips=len(kept), ratio_sum=sum(kept), ratio_sq_sum=sum(r * r for r in kept))
    return factor_and_uncertainty(state)[0]


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    err = predicted - actual
    pct = err / actual * 100
    ss_res, ss_tot = float((err ** 2).sum()), float(((actual - actual.mean()) ** 2).sum())
    return {'trips': int(len(actual)),
            'mae_l': round(float(np.abs(err).mean()), 4),
            'mae_pct': round(float(np.abs(pct).mean()), 2),
            'median_abs_pct': round(float(np.median(np.abs(pct))), 2),
            'bias_pct': round(float(pct.mean()), 2),
            'total_bias_pct': round(float(err.sum() / actual.sum() * 100), 2),
            'r2': round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None}


def sliced(frame, column, methods):
    return {str(key): {m: metrics(g['actual_l'], g[m]) for m in methods}
            for key, g in frame.groupby(column, observed=True) if len(g) >= 20}


# ---------------------------------------------------------------- hybrid residual

HYBRID_FEATURES = ['distance_km', 'planned_speed_kmh', 'turns_per_km', 'climb_m_per_km', 'temp_c',
                   'mass_kg', 'physics_l_per_100km', 'duration_min']


def hybrid_features(frame):
    """Pre-departure features only, in HYBRID_FEATURES order."""
    km = frame['distance_km']
    return pd.DataFrame({
        'distance_km': km,
        'planned_speed_kmh': km / (frame['duration_min'] / 60),
        'turns_per_km': frame['turns'] / km,
        'climb_m_per_km': frame['climb_m'] / km,
        'temp_c': frame['temp_c'],
        'mass_kg': frame['mass_kg'],
        'physics_l_per_100km': frame['physics'] / km * 100,
        'duration_min': frame['duration_min'],
    })[HYBRID_FEATURES]


def residual_model(depth, seed):
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_depth=depth, learning_rate=0.05, max_iter=300,
                                         min_samples_leaf=40, l2_regularization=1.0, random_state=seed)


def fit_hybrid(train, seed):
    """Choose depth by GroupKFold over training vehicles only, then fit on all of them."""
    from sklearn.model_selection import GroupKFold
    X, y, groups = hybrid_features(train), np.log(train['actual_l'] / train['physics']), train['vehicle']
    cv = {}
    for depth in (3, 5):
        errors = []
        for fit_idx, val_idx in GroupKFold(n_splits=5).split(X, y, groups):
            model = residual_model(depth, seed).fit(X.iloc[fit_idx], y.iloc[fit_idx])
            pred = train['physics'].iloc[val_idx] * np.exp(model.predict(X.iloc[val_idx]))
            actual = train['actual_l'].iloc[val_idx]
            errors.append(float((np.abs(pred - actual) / actual).mean() * 100))
        cv[depth] = round(float(np.mean(errors)), 2)
    depth = min(cv, key=cv.get)
    return residual_model(depth, seed).fit(X, y), {'cv_mae_pct_by_max_depth': cv, 'chosen_max_depth': depth}


def run_hybrid(frame, score, learn, holdout, seed):
    from sklearn.inspection import permutation_importance
    train = frame[~frame['vehicle'].isin(holdout)]
    model, selection = fit_hybrid(train, seed)
    test = score[score['vehicle'].isin(holdout)].copy()
    test['hybrid'] = test['physics'] * np.exp(model.predict(hybrid_features(test)))
    learn_h = learn[learn['vehicle'].isin(holdout)].copy()
    learn_h['hybrid'] = learn_h['physics'] * np.exp(model.predict(hybrid_features(learn_h)))
    factors = (learn_h['actual_l'] / learn_h['hybrid']).groupby(learn_h['vehicle']).apply(lambda r: calibration_factor(list(r)))
    test['hybrid_calibrated'] = test['hybrid'] * test['vehicle'].map(factors).fillna(1.0)
    methods = ['hybrid', 'hybrid_calibrated', 'physics', 'physics_calibrated', 'baseline_class_median', 'baseline_own_median']
    importance = permutation_importance(model, hybrid_features(test), np.log(test['actual_l'] / test['physics']),
                                        scoring='neg_mean_absolute_error', n_repeats=10, random_state=seed)
    result = {
        'description': 'physics × exp(gradient-boosted residual); residual target log(actual / physics planning)',
        'features': HYBRID_FEATURES, 'model': 'sklearn HistGradientBoostingRegressor', **selection,
        'train_trips': int(len(train)), 'train_vehicles': int(train['vehicle'].nunique()),
        'holdout_vehicles': len(holdout), 'holdout_scored_trips': int(len(test)),
        'holdout': {m: metrics(test['actual_l'], test[m]) for m in methods},
        'permutation_importance_holdout': dict(sorted(
            {f: round(float(v), 4) for f, v in zip(HYBRID_FEATURES, importance.importances_mean)}.items(),
            key=lambda kv: -kv[1])),
        'slices': {'weight_lb': sliced(test, 'weight_lb', methods), 'trip_length': sliced(test, 'length_bucket', methods),
                   'average_speed': sliced(test, 'speed_bucket', methods)},
    }
    beats = result['holdout']['hybrid']['mae_pct'] < result['holdout']['baseline_class_median']['mae_pct']
    result['beats_class_median_baseline'] = beats
    if beats:
        import joblib
        import sklearn
        models_dir = ROOT / 'app' / 'ml' / 'models'
        models_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, models_dir / 'ved_residual.joblib')
        (models_dir / 'ved_residual.json').write_text(json.dumps({
            'features': HYBRID_FEATURES, 'target': 'log(actual_l / physics_planning_l)',
            'sklearn_version': sklearn.__version__, 'train_trips': result['train_trips'],
            'train_vehicles': result['train_vehicles'], 'holdout': result['holdout'],
            'chosen_max_depth': selection['chosen_max_depth'],
            'applies_to': ['car', 'van'], 'not_for': ['truck', 'heavy_truck'],
            'source': 'VED (US gasoline cars and light trucks); see public_data/ved_evaluation.json',
        }, indent=2), encoding='utf-8')
    result['saved_model'] = 'app/ml/models/ved_residual.joblib' if beats else None
    return result


# ---------------------------------------------------------------- main

def load_vehicles():
    static = pd.read_excel(DATA_DIR / 'VED_Static_Data_ICE&HEV.xlsx')
    static['weight_lb'] = pd.to_numeric(static['Generalized_Weight'], errors='coerce')
    ice = static[(static['Vehicle Type'] == 'ICE') & static['weight_lb'].notna()]
    return {int(r.VehId): float(r.weight_lb) * 0.45359237 for r in ice.itertuples()}, {
        'static_vehicles': int(len(static)), 'ice_vehicles': int((static['Vehicle Type'] == 'ICE').sum()),
        'ice_with_weight': int(len(ice))}


def load_trips(vehicles):
    kept, reasons, seen = [], {}, set()
    for path in sorted((DATA_DIR / 'dynamic').glob('VED_*_week.csv')):
        frame = pd.read_csv(path, usecols=list(COLUMNS)).rename(columns=COLUMNS)
        frame = frame[frame['vehicle'].isin(vehicles)]
        for (vehicle, trip_id), group in frame.groupby(['vehicle', 'trip']):
            key = (int(vehicle), int(trip_id))
            if key in seen:  # a trip split across weekly files is dropped, not stitched
                reasons['split_across_files'] = reasons.get('split_across_files', 0) + 1
                kept = [k for k in kept if (k['vehicle'], k['trip']) != key]
                continue
            seen.add(key)
            trip = integrate_trip(group)
            reason = filter_reason(trip)
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
                continue
            trip.update(vehicle=key[0], trip=key[1], day=float(group['day'].min()),
                        start_ms=float(group['ms'].min()), actual_l=trip['fuel_l'])
            trip['pieces'], trip['turns'] = planning_pieces(trip)
            # Keep only what the post-trip variant needs, compactly (~29 M samples overall).
            for name in ('lat', 'lng', 't'):
                del trip[name]
            for name in ('dt', 'step_m', 'speed'):
                trip[name] = trip[name].astype(np.float32)
            kept.append(trip)
        print(f'{path.name}: {len(kept)} trips kept so far', flush=True)
    return kept, reasons


def run(seed=SEED, post_trip_sample=None):
    started = time.time()
    vehicles, vehicle_counts = load_vehicles()
    trips, excluded = load_trips(vehicles)

    # Temperature: trip mean OAT; else that day's median across vehicles; else overall median.
    day_temp = pd.Series({t['day']: t['temp_c'] for t in trips if not math.isnan(t['temp_c'])})
    day_median = pd.DataFrame({'day': [math.floor(d) for d in day_temp.index], 't': day_temp.values}).groupby('day')['t'].median()
    overall = float(np.nanmedian([t['temp_c'] for t in trips]))
    imputed_temp = 0
    for t in trips:
        if math.isnan(t['temp_c']):
            t['temp_c'] = float(day_median.get(math.floor(t['day']), overall))
            imputed_temp += 1

    cells = sorted({cell(p['start']) for t in trips for p in t['pieces'][:1]} |
                   {cell(p['end']) for t in trips for p in t['pieces']})
    heights, failed_cells = fetch_elevations(cells, DATA_DIR / 'elevation_cache.json')
    flat = 0
    for t in trips:
        t['segments'], has_terrain = with_elevation(t['pieces'], heights)
        flat += not has_terrain

    rows = []
    for t in trips:
        mass = vehicles[t['vehicle']]
        rows.append({'vehicle': t['vehicle'], 'trip': t['trip'], 'day': t['day'], 'start_ms': t['start_ms'],
                     'weight_lb': round(mass / 0.45359237), 'distance_km': t['distance_m'] / 1000,
                     'duration_min': t['duration_s'] / 60, 'actual_l': t['actual_l'],
                     'physics': predict_planning(t, mass), 'turns': t['turns'], 'temp_c': t['temp_c'],
                     'climb_m': sum(max(0.0, p['rise_m']) for p in t['segments']), 'mass_kg': mass})
    frame = pd.DataFrame(rows)
    frame['avg_speed_kmh'] = frame['distance_km'] / (frame['duration_min'] / 60)

    # Vehicle hold-out for the class-level baseline; time split inside every vehicle.
    rng = np.random.default_rng(seed)
    ids = np.array(sorted(frame['vehicle'].unique()))
    holdout = set(rng.choice(ids, size=int(round(len(ids) * HOLDOUT_VEHICLE_SHARE)), replace=False).tolist())
    learn, score = chronological_split(frame)

    train_vehicle_trips = frame[~frame['vehicle'].isin(holdout)]
    class_l_per_km = (train_vehicle_trips['actual_l'] / train_vehicle_trips['distance_km']).groupby(
        train_vehicle_trips['weight_lb']).median()
    global_l_per_km = float((train_vehicle_trips['actual_l'] / train_vehicle_trips['distance_km']).median())
    own_l_per_km = (learn['actual_l'] / learn['distance_km']).groupby(learn['vehicle']).median()
    factors = (learn['actual_l'] / learn['physics']).groupby(learn['vehicle']).apply(lambda r: calibration_factor(list(r)))

    score = score.copy()
    score['physics_calibrated'] = score['physics'] * score['vehicle'].map(factors).fillna(1.0)
    score['baseline_class_median'] = score['distance_km'] * score['weight_lb'].map(class_l_per_km).fillna(global_l_per_km)
    score['baseline_own_median'] = score['distance_km'] * score['vehicle'].map(own_l_per_km)
    score = score[score['baseline_own_median'].notna()]
    score['length_bucket'] = pd.cut(score['distance_km'], [0, 5, 15, 1e9], labels=['<5 km', '5-15 km', '>15 km'])
    score['speed_bucket'] = pd.cut(score['avg_speed_kmh'], [0, 30, 60, 1e9], labels=['<30 km/h', '30-60 km/h', '>60 km/h'])

    # Post-trip variant on the scored trips (optionally a fixed stratified sample).
    by_key = {(t['vehicle'], t['trip']): t for t in trips}
    post = score if post_trip_sample is None else score.groupby('vehicle', group_keys=False).apply(
        lambda g: g.sample(min(len(g), post_trip_sample), random_state=seed))
    post = post.copy()
    post['physics_post_trip'] = [predict_post_trip(by_key[(r.vehicle, r.trip)], vehicles[r.vehicle]) for r in post.itertuples()]

    methods = ['physics', 'physics_calibrated', 'baseline_class_median', 'baseline_own_median']
    holdout_score = score[score['vehicle'].isin(holdout)]
    result = {
        'benchmark': 'Physics road-load model vs MAF-derived fuel on real VED trips; NOT Indian freight trucks',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'model': physics.MODEL_VERSION,
        'applies_to_indian_trucks': False,
        'provenance': manifest(DATA_DIR),
        'ground_truth': 'fuel = MAF·(1+(STFT+LTFT)/100)/14.7 g/s ÷ 745 g/L, integrated over sample intervals ≤ 5 s',
        'vehicle_mapping': 'All ICE vehicles use the physics "car" profile (VED class field is "NO DATA" for most), '
                           'mass = Generalized_Weight + 80 kg driver, gasoline',
        'planning_inputs': 'Path cut into ~200 m pieces with each piece\'s actual elapsed time (smooths stop-and-go), '
                           'terrain from Open-Meteo Elevation at ~110 m grid, trip mean outside-air temperature, '
                           f'turns = heading changes > {TURN_DEG:.0f}° between pieces, dry road',
        'counts': {**vehicle_counts, 'trips_kept': len(trips), 'trips_excluded': excluded,
                   'vehicles_with_kept_trips': int(frame['vehicle'].nunique()),
                   'temperature_imputed_trips': imputed_temp, 'trips_without_terrain': flat,
                   'elevation_cells': len(cells), 'elevation_cells_failed': failed_cells,
                   'learning_trips': int(len(learn)), 'scored_trips': int(len(score)),
                   'holdout_vehicles': len(holdout), 'holdout_scored_trips': int(len(holdout_score)),
                   'post_trip_scored_trips': int(len(post))},
        'split': f'Per vehicle, first {CALIBRATION_SHARE:.0%} of trips (by date) learn calibration and the own-median '
                 f'baseline; the later {1 - CALIBRATION_SHARE:.0%} are scored. {HOLDOUT_VEHICLE_SHARE:.0%} of vehicles '
                 f'(seed {seed}) never contribute to the class-median baseline.',
        'calibration_rule': f'app/services/calibration.py: ratios outside {RATIO_RANGE} rejected, shrinkage prior {PRIOR_TRIPS} trips',
        'headline_holdout_vehicles': {m: metrics(holdout_score['actual_l'], holdout_score[m]) for m in methods},
        'all_scored_trips': {m: metrics(score['actual_l'], score[m]) for m in methods if m != 'baseline_class_median'},
        'post_trip_variant': {'physics_post_trip': metrics(post['actual_l'], post['physics_post_trip']),
                              'physics_planning_same_trips': metrics(post['actual_l'], post['physics'])},
        'slices': {'weight_lb': sliced(score, 'weight_lb', methods[:2] + methods[3:]),
                   'trip_length': sliced(score, 'length_bucket', methods[:2] + methods[3:]),
                   'average_speed': sliced(score, 'speed_bucket', methods[:2] + methods[3:])},
        'calibration_factors': {'median': round(float(factors.median()), 3),
                                'p10': round(float(factors.quantile(0.1)), 3),
                                'p90': round(float(factors.quantile(0.9)), 3)},
        'hybrid': run_hybrid(frame, score, learn, holdout, seed),
        'runtime_seconds': round(time.time() - started, 1),
        'limitations': [
            'US personal cars and light trucks in Ann Arbor, Michigan; not Indian freight trucks or diesel engines.',
            'Gasoline ICE only; hybrids and EVs excluded because engine-off and regeneration break MAF-based fuel.',
            'Ground truth is MAF-derived (stoichiometric assumption), not a fuel meter; enrichment under load is missed.',
            'Planning-style speeds come from the trip itself (per 200 m piece), which is more favourable than a '
            'router\'s typical speeds would be.',
            'Vehicle class, drag area and rolling resistance are the generic "car" profile; VED does not give them.',
            'Generalized_Weight is a bucketed weight, not the measured vehicle mass.',
            'Single fixed split and seed; no confidence intervals.',
            f'Terrain: Open-Meteo free-tier hourly limit left {failed_cells} of {len(cells)} elevation cells unfetched; '
            f'{flat} of {len(trips)} trips were treated as flat (Ann Arbor relief is modest).',
        ],
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--download', action='store_true', help='Download and extract VED first')
    parser.add_argument('--post-trip-sample', type=int, default=None,
                        help='Score the post-trip variant on at most N trips per vehicle')
    args = parser.parse_args()
    if args.download:
        download(DATA_DIR)
    summary = run(post_trip_sample=args.post_trip_sample)
    print(json.dumps({'counts': summary['counts'], 'headline_holdout_vehicles': summary['headline_holdout_vehicles'],
                      'all_scored_trips': summary['all_scored_trips'], 'post_trip_variant': summary['post_trip_variant'],
                      'runtime_seconds': summary['runtime_seconds']}, indent=2))
