"""Multi-stop delivery rounds: order stops to trade travel time against CO2.

The load carried on a leg is the starting load minus every drop already made,
so it depends only on the set of stops visited before that leg. Held-Karp
dynamic programming over (visited set, last stop) is therefore exact for this
load-dependent cost. Exact search is limited to 10 stops (10·2¹⁰ states).
"""
import math
import os

import requests

from app.ml import physics
from app.services.elevation import get_elevations
from app.services.live_context import get_live_context
from app.services.routing import ProviderUnavailable

MAX_STOPS = 10
WEIGHTS = [round(i / 10, 1) for i in range(11)]


def _osrm_base():
    return os.environ.get('OSRM_BASE_URL', 'https://router.project-osrm.org').rstrip('/')


def _coords(points):
    return ';'.join(f'{lng},{lat}' for lat, lng in points)


def osrm_table(points):
    """Duration (s) and distance (m) matrices between all points."""
    try:
        response = requests.get(f'{_osrm_base()}/table/v1/driving/{_coords(points)}',
                                params={'annotations': 'duration,distance'}, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 'Ok':
            raise ValueError('Provider error')
        durations, distances = data['durations'], data['distances']
        n = len(points)
        for matrix in (durations, distances):
            if len(matrix) != n or any(len(row) != n for row in matrix):
                raise ValueError('Bad matrix shape')
            for i, row in enumerate(matrix):
                for j, value in enumerate(row):
                    if value is None or not math.isfinite(float(value)) or value < 0 or (i != j and value == 0):
                        raise ValueError('Unroutable pair')
        return [[float(v) for v in row] for row in durations], [[float(v) for v in row] for row in distances]
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        raise ProviderUnavailable('Routing service could not connect all stops. Nothing was saved; please retry.') from exc


def osrm_path(points):
    """Road geometry through the points in order, or None on failure."""
    try:
        response = requests.get(f'{_osrm_base()}/route/v1/driving/{_coords(points)}',
                                params={'overview': 'simplified', 'geometries': 'geojson'}, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        coords = data['routes'][0]['geometry']['coordinates']
        return [[float(lat), float(lng)] for lng, lat in coords]
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return None


class Round:
    """Cost model for one round. Node 0 is the depot; nodes 1..n are stops."""

    def __init__(self, durations, distances, elevations, drops, start_load, vehicle_key, fuel_key,
                 temp_c, wet_road, return_to_depot, calibration_factor=1.0, use_hybrid=False):
        self.factor = calibration_factor
        # The ML correction was learned from trips of 2 km or more, so shorter legs stay physics-only.
        from app.ml import hybrid
        self.use_hybrid = use_hybrid and hybrid.applies(vehicle_key, fuel_key)
        self.dur, self.dist, self.elev = durations, distances, elevations
        self.drops, self.start_load = drops, start_load
        self.n = len(drops)
        self.vehicle_key, self.fuel_key = vehicle_key, fuel_key
        self.temp_c, self.wet_road, self.back = temp_c, wet_road, return_to_depot
        self._legs = {}

    def load_after(self, mask):
        return self.start_load - sum(self.drops[k] for k in range(self.n) if mask >> k & 1)

    def leg(self, i, j, mask):
        """Physics estimate for driving node i -> node j carrying the load left after `mask`."""
        key = (i, j, mask)
        if key not in self._legs:
            d, t = self.dist[i][j], self.dur[i][j]
            speed = d / t * 3.6
            turns = round(d / 1000 * (1.0 if speed < 35 else 0.3)) + 1
            seg = [{'distance_m': d, 'duration_s': t, 'rise_m': self.elev[j] - self.elev[i],
                    'elevation_m': (self.elev[i] + self.elev[j]) / 2}]
            load = self.load_after(mask)
            result = physics.estimate(seg, self.vehicle_key, self.fuel_key, load,
                                      temp_c=self.temp_c, wet_road=self.wet_road, turns=turns)
            if self.use_hybrid and d >= 2000:
                from app.ml import hybrid
                result, _ = hybrid.apply(result, self.temp_c, t / 60)
            # The learned per-vehicle factor scales every leg equally, so it changes the
            # reported fuel and CO2 but never the optimal order.
            self._legs[key] = dict(result, co2_kg=round(result['co2_kg'] * self.factor, 3),
                                   fuel=round(result['fuel'] * self.factor, 3), load_kg=load, duration_s=t)
        return self._legs[key]

    def solve(self, w=0.0, time_scale=1.0, co2_scale=1.0):
        """Exact order of stop indices (0-based) minimising w·CO2 + (1−w)·time, both normalised."""
        def cost(i, j, mask):
            legc = self.leg(i, j, mask)
            return w * legc['co2_kg'] / co2_scale + (1 - w) * legc['duration_s'] / time_scale

        n, full = self.n, (1 << self.n) - 1
        dp, parent = {}, {}
        for j in range(n):
            dp[(1 << j, j)] = cost(0, j + 1, 0)
        for mask in range(1, full + 1):
            for last in range(n):
                here = dp.get((mask, last))
                if here is None:
                    continue
                for nxt in range(n):
                    if mask >> nxt & 1:
                        continue
                    key = (mask | 1 << nxt, nxt)
                    value = here + cost(last + 1, nxt + 1, mask)
                    if value < dp.get(key, math.inf):
                        dp[key], parent[key] = value, last
        best, best_last = math.inf, None
        for last in range(n):
            value = dp[(full, last)] + (cost(last + 1, 0, full) if self.back else 0)
            if value < best:
                best, best_last = value, last
        order, mask, last = [], full, best_last
        while last is not None:
            order.append(last)
            prev = parent.get((mask, last))
            mask &= ~(1 << last)
            last = prev
        return order[::-1]

    def evaluate(self, order):
        legs, mask, here = [], 0, 0
        for stop in order:
            legs.append((here, stop + 1, mask))
            mask |= 1 << stop
            here = stop + 1
        if self.back:
            legs.append((here, 0, mask))
        rows = []
        for i, j, m in legs:
            legc = self.leg(i, j, m)
            rows.append({'from': 'depot' if i == 0 else i - 1, 'to': 'depot' if j == 0 else j - 1,
                         'distance_km': round(self.dist[i][j] / 1000, 2),
                         'duration_min': round(legc['duration_s'] / 60, 1),
                         'load_kg': round(legc['load_kg'], 1), 'co2_kg': round(legc['co2_kg'], 3),
                         '_fuel': legc['fuel'], '_unit': legc['fuel_unit'], '_s': legc['duration_s'],
                         '_m': self.dist[i][j], '_co2': legc['co2_kg']})
        return {'order': list(order),
                'duration_min': round(sum(r['_s'] for r in rows) / 60, 1),
                'distance_km': round(sum(r['_m'] for r in rows) / 1000, 2),
                'co2_kg': round(sum(r['_co2'] for r in rows), 3),
                'fuel': round(sum(r['_fuel'] for r in rows), 3),
                'fuel_unit': rows[0]['_unit'] if rows else physics.FUELS[self.fuel_key]['unit'],
                'legs': [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]}


def plan_round(depot, stops, vehicle_key, fuel_key, start_load, return_to_depot=True, calibration_factor=1.0):
    """depot: (lat, lng); stops: [{'lat', 'lng', 'drop_kg'}]. Returns plans, pareto and context."""
    points = [depot] + [(s['lat'], s['lng']) for s in stops]
    durations, distances = osrm_table(points)
    assumptions = ['Travel times are normal road times. Live traffic is not included.',
                   'Turns and stops are estimated from the road speed.',
                   f'Fuel is corrected by what the app learned about this vehicle (×{calibration_factor:.2f}).']

    elevations = get_elevations(points)
    elevation_status = 'available'
    if elevations is None:
        elevations = [0.0] * len(points)
        elevation_status = 'unavailable'
        assumptions.append('Terrain unknown: hill data was unavailable, so hills are not counted.')

    context = get_live_context(*depot)
    current = context.get('current') if context.get('status') != 'unavailable' else None
    if current:
        weather = {'temp_c': current['temperature_2m'], 'wet_road': current['precipitation'] > 0.2,
                   'status': context['status']}
    else:
        weather = {'temp_c': 25.0, 'wet_road': False, 'status': 'unavailable'}
        assumptions.append('Weather unavailable: we assumed 25 °C and a dry road.')

    model = Round(durations, distances, elevations, [s['drop_kg'] for s in stops], start_load,
                  vehicle_key, fuel_key, weather['temp_c'], weather['wet_road'], return_to_depot,
                  calibration_factor, use_hybrid=True)
    if model.use_hybrid:
        assumptions.append('Fuel includes the ML correction learned from real petrol-car trips.')
    fastest = model.evaluate(model.solve(0.0))
    time_scale = max(fastest['duration_min'] * 60, 1e-9)
    co2_scale = max(fastest['co2_kg'], 1e-9)

    pareto, seen, results = [], set(), {}
    for w in WEIGHTS:
        order = model.solve(w, time_scale, co2_scale) if w else fastest['order']
        result = fastest if w == 0 else model.evaluate(order)
        results[w] = result
        if tuple(order) not in seen:
            seen.add(tuple(order))
            pareto.append({'weight': w, 'order': order, 'duration_min': result['duration_min'],
                           'co2_kg': result['co2_kg']})
    greenest = results[1.0]
    green_co2 = max(greenest['co2_kg'], 1e-9)
    balanced_point = min(pareto, key=lambda p: p['duration_min'] / fastest['duration_min'] + p['co2_kg'] / green_co2
                         if fastest['duration_min'] else p['co2_kg'] / green_co2)
    balanced = model.evaluate(balanced_point['order'])

    paths, straight = {}, False
    plans = []
    for key, result in (('fastest', fastest), ('greenest', greenest), ('balanced', balanced)):
        order = tuple(result['order'])
        if order not in paths:
            waypoints = [points[0]] + [points[i + 1] for i in order] + ([points[0]] if return_to_depot else [])
            path = osrm_path(waypoints)
            if path is None:
                path, straight = [list(p) for p in waypoints], True
            paths[order] = path
        plans.append(dict(result, key=key, path_points=paths[order]))
    if straight:
        assumptions.append('Road shapes did not load, so the map shows straight lines.')

    saved = fastest['co2_kg'] - greenest['co2_kg']
    return {'plans': plans, 'pareto': pareto,
            'savings_vs_fastest': {'co2_kg': round(saved, 3),
                                   'percent': round(saved / fastest['co2_kg'] * 100, 1) if fastest['co2_kg'] else 0.0,
                                   'extra_minutes': round(greenest['duration_min'] - fastest['duration_min'], 1)},
            'elevation_status': elevation_status, 'weather': weather,
            'model': physics.MODEL_VERSION, 'assumptions': assumptions}
