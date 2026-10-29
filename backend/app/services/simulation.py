"""Fleet simulation sandbox: a synthetic day of deliveries in Bengaluru.

SIMULATION ONLY. Orders, traffic multipliers and each truck's "true" fuel
behaviour are generated here from a seed. The roads, distances and terrain are
real (OSRM, Open-Meteo), and every round is ordered by the same Held-Karp
planner the app uses. This demonstrates operations at fleet scale and how the
calibration loop behaves; it says nothing about model accuracy on real trucks.

Nothing here touches the database. The scenario lives in one in-memory
singleton per server process.
"""
import math
import random
import threading
import time
from types import SimpleNamespace

import requests

from app.ml import physics
from app.services import calibration
from app.services.elevation import get_elevations
from app.services.live_context import get_live_context
from app.services.rounds import Round, osrm_path, _osrm_base, _coords

LABEL = 'SIMULATION'
DEPOTS = {
    'Peenya': (13.0285, 77.5197),
    'Hoskote': (13.0707, 77.7982),
    'Electronic City': (12.8452, 77.6602),
}
LOCALITIES = {
    'Malleshwaram': (13.0035, 77.5710), 'Rajajinagar': (12.9910, 77.5520), 'Yeshwanthpur': (13.0285, 77.5400),
    'Hebbal': (13.0358, 77.5970), 'Jayanagar': (12.9308, 77.5838), 'JP Nagar': (12.9063, 77.5857),
    'BTM Layout': (12.9166, 77.6101), 'Koramangala': (12.9352, 77.6245), 'HSR Layout': (12.9121, 77.6446),
    'Indiranagar': (12.9784, 77.6408), 'Whitefield': (12.9698, 77.7500), 'Marathahalli': (12.9569, 77.7011),
    'Bellandur': (12.9260, 77.6762), 'Banashankari': (12.9255, 77.5468), 'Basavanagudi': (12.9417, 77.5755),
    'MG Road': (12.9756, 77.6066), 'Shivajinagar': (12.9857, 77.6057), 'Frazer Town': (12.9988, 77.6150),
    'RT Nagar': (13.0213, 77.5950), 'Yelahanka': (13.1007, 77.5963), 'Vijayanagar': (12.9719, 77.5370),
    'Kengeri': (12.9081, 77.4853), 'Banaswadi': (13.0104, 77.6482), 'KR Puram': (13.0077, 77.6956),
    'Mahadevapura': (12.9911, 77.6896), 'Bommanahalli': (12.9030, 77.6240), 'Hennur': (13.0358, 77.6400),
    'Jalahalli': (13.0450, 77.5480), 'Nagarbhavi': (12.9600, 77.5100), 'Ulsoor': (12.9817, 77.6286),
    'Domlur': (12.9610, 77.6387), 'Sarjapur Road': (12.9100, 77.6850), 'Kalyan Nagar': (13.0220, 77.6400),
    'Sadashivanagar': (13.0068, 77.5813), 'Vasanth Nagar': (12.9880, 77.5940), 'Wilson Garden': (12.9480, 77.5970),
    'Bannerghatta Road': (12.8900, 77.5970), 'Hosur Road': (12.8760, 77.6400), 'Kadugodi': (12.9980, 77.7600),
    'Varthur': (12.9400, 77.7470),
}
# Fleet mix: (class, share, capacity range kg, fuel choices with weights)
FLEET_MIX = [
    ('van', 0.60, (1000, 1500), [('diesel', 0.6), ('cng', 0.25), ('electric', 0.15)]),
    ('truck', 0.30, (6000, 8000), [('diesel', 0.9), ('cng', 0.1)]),
    ('heavy_truck', 0.10, (15000, 15000), [('diesel', 1.0)]),
]
# ASSUMPTION, not measured: travel time = OSRM free-flow time x multiplier for the hour.
TRAFFIC = [
    {'from': 0, 'to': 6, 'multiplier': 1.0, 'label': 'Night'},
    {'from': 6, 'to': 8, 'multiplier': 1.1, 'label': 'Early morning'},
    {'from': 8, 'to': 11, 'multiplier': 1.7, 'label': 'Morning peak'},
    {'from': 11, 'to': 17, 'multiplier': 1.3, 'label': 'Daytime'},
    {'from': 17, 'to': 21, 'multiplier': 1.8, 'label': 'Evening peak'},
    {'from': 21, 'to': 24, 'multiplier': 1.0, 'label': 'Late evening'},
]
MAX_STOPS = 8
CHUNK = 80                 # orders per OSRM table request (plus the depot)
SERVICE_MIN = 8            # unloading time at each stop
LOAD_MIN = 30              # reloading at the depot between rounds
DAY_START, DAY_END = 5 * 60 + 30, 22 * 60
HEAVY_ORDER_KG = 1200
REPLAY_DAYS = 30
OSRM_INTERVAL_S = 1.05     # public OSRM server policy: at most about one request per second

_lock = threading.Lock()
_state = {'phase': 'idle', 'progress': 0.0, 'message': 'No simulation yet.', 'osrm_requests': 0,
          'scenario': None, 'error': None}
_last_request = [0.0]


# ── Small helpers ──────────────────────────────────────────────────────────────

def _haversine_m(a, b):
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def traffic_multiplier(minute_of_day):
    hour = (minute_of_day / 60) % 24
    return next(row['multiplier'] for row in TRAFFIC if row['from'] <= hour < row['to'])


def _throttled(call):
    """Run one OSRM request no faster than the public server allows, and count it."""
    wait = OSRM_INTERVAL_S - (time.monotonic() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    _last_request[0] = time.monotonic()
    with _lock:
        _state['osrm_requests'] += 1
    return call()


def _progress(fraction, message):
    with _lock:
        _state['progress'], _state['message'] = round(fraction, 3), message


def osrm_matrix(points):
    """Durations (s) and distances (m) between points. Unroutable pairs become None."""
    response = requests.get(f'{_osrm_base()}/table/v1/driving/{_coords(points)}',
                            params={'annotations': 'duration,distance'}, timeout=(5, 30))
    response.raise_for_status()
    data = response.json()
    if data.get('code') != 'Ok':
        raise ValueError('OSRM table error')
    clean = lambda m: [[None if v is None else max(float(v), 1.0) for v in row] for row in m]
    return clean(data['durations']), clean(data['distances'])


# ── Scenario generation ────────────────────────────────────────────────────────

def make_fleet(rng, count, depot_shares):
    trucks, depot_names = [], list(DEPOTS)
    for i in range(count):
        roll, cumulative = rng.random(), 0.0
        for vehicle_key, share, (low, high), fuels in FLEET_MIX:
            cumulative += share
            if roll < cumulative:
                break
        fuel = rng.choices([f for f, _ in fuels], weights=[w for _, w in fuels])[0]
        trucks.append({
            'id': i + 1, 'plate': f'KA-{rng.randint(1, 53):02d}-{rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")}'
                                 f'{rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ")}-{rng.randint(1000, 9999)}',
            'class': vehicle_key, 'class_label': physics.PROFILES[vehicle_key]['label'], 'fuel': fuel,
            'capacity_kg': round(rng.uniform(low, high), -2),
            # Synthetic "truth": how this vehicle really consumes vs the class physics.
            'hidden_factor': round(math.exp(rng.gauss(0, 0.12)), 3),
        })
    # Split every vehicle class across depots in proportion to each depot's load
    # (largest remainder), so a small depot still gets its share of big trucks.
    total = sum(depot_shares.values())
    for vehicle_key, *_ in FLEET_MIX:
        group = [t for t in trucks if t['class'] == vehicle_key]
        quotas = {d: len(group) * depot_shares[d] / total for d in depot_names}
        counts = {d: int(q) for d, q in quotas.items()}
        for d in sorted(depot_names, key=lambda d: quotas[d] - counts[d], reverse=True)[:len(group) - sum(counts.values())]:
            counts[d] += 1
        labels = [d for d in depot_names for _ in range(counts[d])]
        rng.shuffle(labels)
        for truck, depot in zip(group, labels):
            truck['depot'] = depot
    return trucks


def make_orders(rng, count):
    names = list(LOCALITIES)
    orders = []
    for i in range(count):
        place = rng.choice(names)
        lat, lng = LOCALITIES[place]
        roll = rng.random()
        if roll < 0.70:
            weight = rng.uniform(30, 250)
        elif roll < 0.95:
            weight = rng.uniform(300, 1200)
        else:
            weight = rng.uniform(1500, 4000)
        point = (round(lat + rng.uniform(-0.004, 0.004), 5), round(lng + rng.uniform(-0.004, 0.004), 5))
        depot = min(DEPOTS, key=lambda d: _haversine_m(point, DEPOTS[d]))
        orders.append({'id': i + 1, 'label': place, 'lat': point[0], 'lng': point[1],
                       'drop_kg': round(weight), 'depot': depot})
    return orders


def sweep_chunks(orders, depot):
    """Orders of one depot sorted by bearing (sweep), cut into contiguous chunks."""
    centre = DEPOTS[depot]
    mine = sorted((o for o in orders if o['depot'] == depot),
                  key=lambda o: math.atan2(o['lat'] - centre[0], o['lng'] - centre[1]))
    return [mine[i:i + CHUNK] for i in range(0, len(mine), CHUNK)]


def pack_rounds(chunk, slots):
    """Fill truck rounds from one sweep chunk. Heavy orders go first so they get big vehicles.

    slots: list of trucks still able to take a round (mutated: used slots are removed).
    Returns [(truck, [orders])] and the orders that did not fit any slot.
    """
    remaining = sorted(chunk, key=lambda o: o['drop_kg'] < HEAVY_ORDER_KG)  # stable: heavy first, sweep kept
    rounds, left = [], []
    while remaining and slots:
        first = remaining[0]
        fits = [t for t in slots if t['capacity_kg'] >= first['drop_kg']]
        if not fits:
            left.append(remaining.pop(0))
            continue
        truck = max(fits, key=lambda t: t['capacity_kg']) if first['drop_kg'] >= HEAVY_ORDER_KG else fits[0]
        slots.remove(truck)
        taken, load = [], 0
        for order in list(remaining):
            if len(taken) == MAX_STOPS:
                break
            if load + order['drop_kg'] <= truck['capacity_kg']:
                taken.append(order)
                load += order['drop_kg']
                remaining.remove(order)
        rounds.append((truck, taken))
    return rounds, left + remaining


def idling(truck, seconds, temp_c):
    """Fuel and CO2 for standing in traffic: accessories and AC keep running, as in physics.estimate."""
    profile, power, fuel = physics.PROFILES[truck['class']], physics.POWERTRAINS[truck['fuel']], physics.FUELS[truck['fuel']]
    ac_share = min(1.0, max(0.0, (temp_c - 24) / 8))
    megajoules = (profile['aux_kw'] + profile['ac_kw'] * ac_share) * 1000 * seconds / power['aux'] / 1e6
    quantity = megajoules / fuel['mj_per_unit']
    return quantity, quantity * fuel['co2_kg_per_unit']


def plan_and_execute(rng, truck, stops, matrix, elevations, weather, depart_min):
    """Order one round with the app's planner (free-flow), then drive it in simulated traffic."""
    durations, distances = matrix
    start_load = sum(s['drop_kg'] for s in stops)
    model = Round(durations, distances, elevations, [s['drop_kg'] for s in stops], start_load,
                  truck['class'], truck['fuel'], weather['temp_c'], weather['wet_road'], True)
    fastest = model.evaluate(model.solve(0.0))
    time_scale = max(fastest['duration_min'] * 60, 1e-9)
    co2_scale = max(fastest['co2_kg'], 1e-9)
    candidates = [fastest] + [model.evaluate(model.solve(w, time_scale, co2_scale)) for w in (0.25, 0.5, 0.75, 1.0)]
    greenest = candidates[-1]
    chosen = min(candidates, key=lambda r: r['duration_min'] / max(fastest['duration_min'], 1e-9)
                 + r['co2_kg'] / max(greenest['co2_kg'], 1e-9))

    # Execute: traffic for the hour each leg starts, plus seeded noise per leg.
    clock, legs, nodes = depart_min, [], [0] + [i + 1 for i in chosen['order']] + [0]
    for leg_index, (a, b) in enumerate(zip(nodes, nodes[1:])):
        planned = chosen['legs'][leg_index]
        multiplier = traffic_multiplier(clock) * math.exp(rng.gauss(0, 0.1))
        free_s, metres = durations[a][b], distances[a][b]
        actual_s = free_s * multiplier
        # Congestion = moving at normal road speed with more stop-and-go cycles, plus standing
        # still for the extra time. (Using the slow average speed would wrongly cut drag and
        # stop-go energy, making traffic look cleaner.)
        base_turns = 1.0 if metres / free_s * 3.6 < 35 else 0.3
        segment = [{'distance_m': metres, 'duration_s': free_s, 'rise_m': elevations[b] - elevations[a],
                    'elevation_m': (elevations[a] + elevations[b]) / 2}]
        driven = physics.estimate(segment, truck['class'], truck['fuel'], planned['load_kg'],
                                  temp_c=weather['temp_c'], wet_road=weather['wet_road'],
                                  turns=round(metres / 1000 * base_turns * max(multiplier, 1.0)) + 1)
        idle_fuel, idle_co2 = idling(truck, max(0.0, actual_s - free_s), weather['temp_c'])
        fuel = driven['fuel'] + idle_fuel
        legs.append({'from': a, 'to': b, 'start_min': round(clock, 2), 'drive_min': round(actual_s / 60, 2),
                     'distance_km': round(metres / 1000, 2), 'load_kg': planned['load_kg'],
                     'traffic': round(multiplier, 2), 'physics_fuel': round(fuel, 4),
                     'co2_kg': round((driven['co2_kg'] + idle_co2) * truck['hidden_factor'], 3),
                     'fuel': round(fuel * truck['hidden_factor'], 3)})
        clock += actual_s / 60 + (SERVICE_MIN if b != 0 else 0)

    physics_fuel = sum(l['physics_fuel'] for l in legs)
    reported = physics_fuel * truck['hidden_factor'] * math.exp(rng.gauss(0, 0.06))
    bad = rng.random() < 0.02
    if bad:
        reported *= rng.choice([5.0, 0.1])
    return {
        'truck_id': truck['id'], 'depot': truck['depot'], 'depart_min': depart_min, 'return_min': round(clock, 2),
        'stops': [stops[i] for i in chosen['order']],
        'planned': {'fastest_co2_kg': fastest['co2_kg'], 'greenest_co2_kg': greenest['co2_kg'],
                    'chosen_co2_kg': chosen['co2_kg'], 'chosen_fuel': chosen['fuel'],
                    'fastest_min': fastest['duration_min'], 'chosen_min': chosen['duration_min']},
        'legs': legs, 'fuel_unit': chosen['fuel_unit'],
        'executed': {'co2_kg': round(sum(l['co2_kg'] for l in legs), 3),
                     'fuel': round(sum(l['fuel'] for l in legs), 3),
                     'distance_km': round(sum(l['distance_km'] for l in legs), 2),
                     'physics_fuel': round(physics_fuel, 3)},
        'reported_fuel': round(reported, 3), 'bad_report': bad,
        'nodes': [DEPOTS[truck['depot']]] + [(stops[i]['lat'], stops[i]['lng']) for i in chosen['order']],
        'path': None,
    }


def calibrate(trucks, rounds, rng, days=REPLAY_DAYS):
    """Run the app's calibration formula on each truck's reports over `days` replayed days.

    Day 1 uses the simulated reports; later days resample report noise (and the 2%
    bad reports) on the same rounds. Returns the convergence series and per-truck results.
    """
    by_truck = {t['id']: [r for r in rounds if r['truck_id'] == t['id']] for t in trucks}
    stats = {t['id']: SimpleNamespace(trips=0, ratio_sum=0.0, ratio_sq_sum=0.0, rejected=0) for t in trucks}
    active = [t for t in trucks if by_truck[t['id']]]
    error = lambda: sum(abs(calibration.factor_and_uncertainty(stats[t['id']])[0] - t['hidden_factor'])
                        for t in active) / max(len(active), 1)
    series = [{'trips_per_truck': 0, 'mean_abs_error': round(error(), 4)}]
    rejected = 0
    for day in range(days):
        for truck in active:
            for r in by_truck[truck['id']]:
                if day == 0:
                    reported = r['reported_fuel']
                else:
                    reported = r['executed']['physics_fuel'] * truck['hidden_factor'] * math.exp(rng.gauss(0, 0.06))
                    if rng.random() < 0.02:
                        reported *= rng.choice([5.0, 0.1])
                ratio = reported / r['executed']['physics_fuel']
                s = stats[truck['id']]
                if not calibration.RATIO_RANGE[0] <= ratio <= calibration.RATIO_RANGE[1]:
                    s.rejected += 1
                    rejected += 1
                    continue
                s.trips += 1
                s.ratio_sum += ratio
                s.ratio_sq_sum += ratio * ratio
        trips = round(sum(len(by_truck[t['id']]) for t in active) / max(len(active), 1) * (day + 1), 1)
        series.append({'trips_per_truck': trips, 'mean_abs_error': round(error(), 4)})
        if day == 0:
            first_day = {tid: calibration.factor_and_uncertainty(s)[0] for tid, s in stats.items()}
    learned = {tid: calibration.factor_and_uncertainty(s)[0] for tid, s in stats.items()}
    baseline = sum(abs(1 - t['hidden_factor']) for t in active) / max(len(active), 1)
    return {'series': series, 'no_learning_error': round(baseline, 4), 'rejected_reports': rejected,
            'replay_days': days, 'first_day': first_day, 'learned': learned}


def build_scenario(trucks=150, orders=900, seed=7, progress=_progress, throttled=_throttled):
    rng = random.Random(seed)
    started = time.monotonic()
    order_list = make_orders(rng, orders)
    load_by_depot = {d: sum(o['drop_kg'] for o in order_list if o['depot'] == d) or 1 for d in DEPOTS}
    fleet = make_fleet(rng, trucks, load_by_depot)

    progress(0.02, 'Reading live weather in Bengaluru')
    context = get_live_context(*DEPOTS['Peenya'])
    current = context.get('current') if context.get('status') != 'unavailable' else None
    weather = ({'temp_c': current['temperature_2m'], 'wet_road': current['precipitation'] > 0.2, 'status': context['status']}
               if current else {'temp_c': 25.0, 'wet_road': False, 'status': 'unavailable'})

    progress(0.05, 'Fetching terrain for every stop')
    # One terrain lookup per depot and locality (43 points, one request): Open-Meteo's free
    # tier counts every coordinate, and orders sit within ~400 m of their locality centre.
    names = list(DEPOTS) + list(LOCALITIES)
    heights = get_elevations([DEPOTS.get(n) or LOCALITIES[n] for n in names])
    elevation_status = 'available' if heights else 'unavailable'
    by_name = dict(zip(names, heights)) if heights else {}
    height_of = {DEPOTS[d]: by_name.get(d, 0.0) for d in DEPOTS}
    height_of.update({(o['lat'], o['lng']): by_name.get(o['label'], 0.0) for o in order_list})

    chunks = [(d, c) for d in DEPOTS for c in sweep_chunks(order_list, d)]
    rounds, unassigned, unroutable = [], [], []
    # Every truck can run a first round, then a second one once all first rounds at its depot are used.
    first_round = {d: [t for t in fleet if t['depot'] == d] for d in DEPOTS}
    second_round = {d: list(first_round[d]) for d in DEPOTS}
    for index, (depot, chunk) in enumerate(chunks):
        progress(0.08 + 0.85 * index / max(len(chunks), 1), f'Road distances and planning: {depot} ({index + 1}/{len(chunks)})')
        pts = [DEPOTS[depot]] + [(o['lat'], o['lng']) for o in chunk]
        durations, distances = throttled(lambda: osrm_matrix(pts))
        routable = [o for k, o in enumerate(chunk) if durations[0][k + 1] is not None and durations[k + 1][0] is not None]
        unroutable += [o for o in chunk if o not in routable]
        packed, left = pack_rounds(routable, first_round[depot])
        more, left = pack_rounds(left, second_round[depot])
        unassigned += left
        for truck, stops in packed + more:
            idx = [0] + [chunk.index(o) + 1 for o in stops]
            sub = lambda m: [[m[a][b] for b in idx] for a in idx]
            sub_d, sub_m = sub(durations), sub(distances)
            if any(v is None for row in sub_d for v in row):
                unroutable += stops
                continue
            elev = [height_of.get(pts[k], 0.0) for k in idx]
            done = [r for r in rounds if r['truck_id'] == truck['id']]
            depart = done[-1]['return_min'] + LOAD_MIN if done else DAY_START + 30 + rng.uniform(0, 480)
            rounds.append(plan_and_execute(rng, truck, stops, (sub_d, sub_m), elev, weather, round(depart, 2)))

    progress(0.95, 'Running the calibration loop')
    cal = calibrate(fleet, rounds, random.Random(seed + 1))
    for truck in fleet:
        truck['learned_factor_day1'] = round(cal['first_day'][truck['id']], 3)
        truck['learned_factor_30d'] = round(cal['learned'][truck['id']], 3)
        truck['rounds'] = [i for i, r in enumerate(rounds) if r['truck_id'] == truck['id']]

    return {
        'label': LABEL, 'seed': seed, 'built_in_s': round(time.monotonic() - started, 1),
        'trucks': fleet, 'orders': order_list, 'rounds': rounds,
        'unassigned_orders': [o['id'] for o in unassigned], 'unroutable_orders': [o['id'] for o in unroutable],
        'weather': weather, 'elevation_status': elevation_status, 'calibration': {
            'series': cal['series'], 'no_learning_error': cal['no_learning_error'],
            'rejected_reports': cal['rejected_reports'], 'replay_days': cal['replay_days']},
    }


# ── Background run and lazy road geometry ──────────────────────────────────────

def _run(params):
    try:
        scenario = build_scenario(**params)
        with _lock:
            _state.update(phase='ready', progress=1.0, scenario=scenario,
                          message='Scenario ready. Road shapes load in the background.')
        for r in sorted(scenario['rounds'], key=lambda r: r['depart_min']):
            with _lock:
                if _state['scenario'] is not scenario:
                    return                                   # reset or restarted
            waypoints = r['nodes'] + [r['nodes'][0]]
            r['path'] = _throttled(lambda: osrm_path(waypoints))
    except Exception as exc:                                 # surface any failure to the UI
        with _lock:
            _state.update(phase='failed', error=str(exc) or type(exc).__name__,
                          message='Simulation build failed. Check the network and retry.')


def start(trucks, orders, seed):
    with _lock:
        if _state['phase'] == 'building':
            raise ValueError('A simulation is already being built.')
        _state.update(phase='building', progress=0.0, message='Starting', osrm_requests=0, scenario=None, error=None)
    threading.Thread(target=_run, args=({'trucks': trucks, 'orders': orders, 'seed': seed},), daemon=True).start()


def reset():
    with _lock:
        _state.update(phase='idle', progress=0.0, message='No simulation yet.', osrm_requests=0, scenario=None, error=None)


def status():
    with _lock:
        scenario = _state['scenario']
        paths = sum(1 for r in scenario['rounds'] if r['path']) if scenario else 0
        return {'label': LABEL, 'phase': _state['phase'], 'progress': _state['progress'],
                'message': _state['message'], 'error': _state['error'], 'osrm_requests': _state['osrm_requests'],
                'road_shapes': {'loaded': paths, 'total': len(scenario['rounds']) if scenario else 0},
                'day': {'start_min': DAY_START, 'end_min': DAY_END}}


def scenario():
    with _lock:
        return _state['scenario']


# ── Positions and KPIs at a simulated time ─────────────────────────────────────

def _along(polyline, fraction):
    """Point at `fraction` of the polyline's length."""
    lengths = [_haversine_m(a, b) for a, b in zip(polyline, polyline[1:])]
    target, walked = fraction * sum(lengths), 0.0
    for (a, b), length in zip(zip(polyline, polyline[1:]), lengths):
        if walked + length >= target and length > 0:
            f = (target - walked) / length
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        walked += length
    return tuple(polyline[-1])


def round_at(r, t):
    """(status, lat, lng, load_kg, delivered stops, km driven, CO2 so far, fuel so far) for one round at time t."""
    if t < r['depart_min']:
        return None
    total_km = sum(l['distance_km'] for l in r['legs']) or 1e-9
    km = co2 = fuel = 0.0
    delivered = 0
    for index, leg in enumerate(r['legs']):
        arrive = leg['start_min'] + leg['drive_min']
        last = index == len(r['legs']) - 1
        if t < arrive:
            share = (t - leg['start_min']) / max(leg['drive_min'], 1e-9)
            km += leg['distance_km'] * share
            co2 += leg['co2_kg'] * share
            fuel += leg['fuel'] * share
            line = r['path'] or [list(p) for p in r['nodes'] + [r['nodes'][0]]]
            lat, lng = _along(line, km / total_km)
            return ('returning' if last else 'driving', lat, lng, leg['load_kg'], delivered, km, co2, fuel)
        km += leg['distance_km']
        co2 += leg['co2_kg']
        fuel += leg['fuel']
        if last:
            break
        delivered += 1
        if t < arrive + SERVICE_MIN:
            stop = r['stops'][index]
            return ('delivering', stop['lat'], stop['lng'], leg['load_kg'] - stop['drop_kg'], delivered, km, co2, fuel)
    depot = r['nodes'][0]
    return ('done', depot[0], depot[1], 0.0, delivered, km, co2, fuel)


def state_at(t):
    sc = scenario()
    if not sc:
        return None
    trucks, delivered, in_progress, km_total, co2_total, saved, on_road = [], 0, 0, 0.0, 0.0, 0.0, 0
    fuel_by_type = {}
    for truck in sc['trucks']:
        rounds = [sc['rounds'][i] for i in truck['rounds']]
        status, lat, lng, load, round_id = 'idle', *DEPOTS[truck['depot']], 0.0, None
        for i, r in zip(truck['rounds'], rounds):
            result = round_at(r, t)
            if result is None:
                continue
            state, lat, lng, load, done, km, co2, fuel = result
            delivered += done
            km_total += km
            co2_total += co2
            unit = f"{truck['fuel']} ({r['fuel_unit']})"
            fuel_by_type[unit] = fuel_by_type.get(unit, 0.0) + fuel
            if state == 'done':
                saved += r['planned']['fastest_co2_kg'] - r['planned']['chosen_co2_kg']
                status, round_id = ('done' if i == truck['rounds'][-1] else 'idle'), i
            else:
                status, round_id = state, i
                in_progress += len(r['stops']) - done
        if status in ('driving', 'delivering', 'returning'):
            on_road += 1
        trucks.append({'id': truck['id'], 'plate': truck['plate'], 'class': truck['class'], 'fuel': truck['fuel'],
                       'depot': truck['depot'], 'lat': round(lat, 5), 'lng': round(lng, 5), 'status': status,
                       'load_kg': round(load), 'round_id': round_id})
    return {'label': LABEL, 'sim_time': t, 'traffic_multiplier': traffic_multiplier(t), 'trucks': trucks,
            'depots': [{'name': n, 'lat': p[0], 'lng': p[1]} for n, p in DEPOTS.items()],
            'kpis': {'orders_total': len(sc['orders']), 'delivered': delivered, 'in_progress': in_progress,
                     'distance_km': round(km_total, 1), 'co2_kg': round(co2_total, 1),
                     'co2_saved_vs_fastest_kg': round(saved, 2), 'on_road': on_road,
                     'fuel_by_type': {k: round(v, 1) for k, v in fuel_by_type.items()}}}


def summary():
    sc = scenario()
    if not sc:
        return None
    rounds = sc['rounds']

    def group(key):
        rows = {}
        for r in rounds:
            truck = sc['trucks'][r['truck_id'] - 1]
            k = truck[key] if key != 'depot' else r['depot']
            row = rows.setdefault(k, {'rounds': 0, 'orders': 0, 'distance_km': 0.0, 'co2_kg': 0.0,
                                      'planned_fastest_co2_kg': 0.0, 'planned_chosen_co2_kg': 0.0})
            row['rounds'] += 1
            row['orders'] += len(r['stops'])
            row['distance_km'] += r['executed']['distance_km']
            row['co2_kg'] += r['executed']['co2_kg']
            row['planned_fastest_co2_kg'] += r['planned']['fastest_co2_kg']
            row['planned_chosen_co2_kg'] += r['planned']['chosen_co2_kg']
        return {k: {f: round(v, 1) if isinstance(v, float) else v for f, v in row.items()} for k, row in rows.items()}

    fastest = sum(r['planned']['fastest_co2_kg'] for r in rounds)
    greenest = sum(r['planned']['greenest_co2_kg'] for r in rounds)
    chosen = sum(r['planned']['chosen_co2_kg'] for r in rounds)
    planned_total = sum(r['planned']['chosen_co2_kg'] for r in rounds)
    executed_total = sum(r['executed']['co2_kg'] for r in rounds)
    return {
        'label': LABEL, 'seed': sc['seed'], 'built_in_s': sc['built_in_s'], 'trucks': len(sc['trucks']),
        'trucks_used': len({r['truck_id'] for r in rounds}), 'orders': len(sc['orders']), 'rounds': len(rounds),
        'unassigned_orders': len(sc['unassigned_orders']), 'unroutable_orders': len(sc['unroutable_orders']),
        'by_depot': group('depot'), 'by_class': group('class'),
        'planning': {'fastest_co2_kg': round(fastest, 1), 'greenest_co2_kg': round(greenest, 1),
                     'balanced_co2_kg': round(chosen, 1),
                     'balanced_saving_percent': round((fastest - chosen) / fastest * 100, 2) if fastest else 0.0,
                     'greenest_saving_percent': round((fastest - greenest) / fastest * 100, 2) if fastest else 0.0},
        'traffic_effect': {'planned_free_flow_co2_kg': round(planned_total, 1),
                           'simulated_actual_co2_kg': round(executed_total, 1)},
        'traffic': TRAFFIC, 'weather': sc['weather'], 'elevation_status': sc['elevation_status'],
        'calibration': sc['calibration'],
        'assumptions': [
            'Orders, delivery points and the fleet are made up for the demo. They are not real bookings.',
            'Roads, distances and hills are real (OSRM, Open-Meteo). Weather is live.',
            'Traffic is our guess for each time of day, not measured.',
            "Each truck has a secret 'true' fuel use. Drivers' reports are based on it, and 2% are deliberately wrong to test the filter.",
            f'Each round has up to {MAX_STOPS} stops. Our planner picks the best order without knowing the traffic.',
            f'Trucks leave between 06:00 and 14:00. Each delivery takes {SERVICE_MIN} min, reloading {LOAD_MIN} min.',
            f'The learning chart repeats the same day {REPLAY_DAYS} times.',
            'This shows how the system works. It is not evidence of accuracy on real trucks.',
        ],
    }


def truck_detail(truck_id):
    sc = scenario()
    if not sc or not 1 <= truck_id <= len(sc['trucks']):
        return None
    truck = sc['trucks'][truck_id - 1]
    rounds = []
    for i in truck['rounds']:
        r = sc['rounds'][i]
        rounds.append({'round_id': i, 'depart_min': r['depart_min'], 'return_min': r['return_min'],
                       'stops': [{'label': s['label'], 'drop_kg': s['drop_kg'], 'lat': s['lat'], 'lng': s['lng']} for s in r['stops']],
                       'legs': [{k: l[k] for k in ('start_min', 'drive_min', 'distance_km', 'load_kg', 'traffic', 'co2_kg')} for l in r['legs']],
                       'predicted_fuel': r['planned']['chosen_fuel'], 'reported_fuel': r['reported_fuel'],
                       'fuel_unit': r['fuel_unit'], 'bad_report': r['bad_report'],
                       'planned_co2_kg': r['planned']['chosen_co2_kg'], 'simulated_co2_kg': r['executed']['co2_kg'],
                       'path': r['path'] or [list(p) for p in r['nodes'] + [r['nodes'][0]]]})
    return {'label': LABEL, **{k: truck[k] for k in ('id', 'plate', 'class', 'class_label', 'fuel', 'capacity_kg', 'depot',
                                                     'hidden_factor', 'learned_factor_day1', 'learned_factor_30d')},
            'rounds': rounds}
