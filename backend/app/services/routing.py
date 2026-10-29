"""Road alternatives from OSRM. No invented traffic or weather observations."""
import math
import os
import requests

CITIES = {
    'bengaluru': (12.9716, 77.5946), 'bangalore': (12.9716, 77.5946),
    'mysuru': (12.2958, 76.6394), 'mysore': (12.2958, 76.6394),
    'chennai': (13.0827, 80.2707), 'mumbai': (19.0760, 72.8777),
    'delhi': (28.6139, 77.2090), 'pune': (18.5204, 73.8567),
    'hyderabad': (17.3850, 78.4867), 'hosur': (12.7409, 77.8253),
    'tumakuru': (13.3379, 77.1173), 'kochi': (9.9312, 76.2673),
}


class ProviderUnavailable(Exception):
    pass


def coordinates(place):
    if not isinstance(place, str) or len(place) > 255:
        raise ValueError('Enter a supported city or latitude,longitude.')
    key = place.strip().lower()
    if key in CITIES:
        return CITIES[key]
    try:
        lat, lng = map(float, key.split(','))
        if math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180:
            return lat, lng
    except (ValueError, TypeError):
        pass
    raise ValueError('Location not recognized. Choose a listed city or enter latitude,longitude.')


MAX_SEGMENTS = 99      # 100 elevation samples = one Open-Meteo request per route
MAX_PATH_POINTS = 400  # enough for the map, small enough to store with the plan
SLOWDOWN_MANEUVERS = {'turn', 'end of road', 'fork', 'roundabout', 'rotary', 'roundabout turn', 'exit roundabout', 'exit rotary'}


def _thin(points, limit):
    if len(points) <= limit:
        return points
    step = (len(points) - 1) / (limit - 1)
    return [points[round(i * step)] for i in range(limit)]


def _segments(points, distances, durations):
    """Group OSRM's per-edge annotations into at most MAX_SEGMENTS stretches of similar length."""
    total = sum(distances)
    bins = min(MAX_SEGMENTS, len(distances))
    cuts, travelled, target = [0], 0.0, total / bins
    for i, d in enumerate(distances):
        travelled += d
        if travelled >= target * len(cuts) and len(cuts) < bins:
            cuts.append(i + 1)
    cuts.append(len(distances))
    cuts = sorted(set(cuts))
    segments = []
    for a, b in zip(cuts, cuts[1:]):
        segments.append({'start': points[a], 'end': points[b],
                         'distance_m': sum(distances[a:b]), 'duration_s': sum(durations[a:b])})
    return segments


def _with_elevation(segments):
    from app.services.elevation import get_elevations
    heights = get_elevations([segments[0]['start']] + [s['end'] for s in segments])
    for i, seg in enumerate(segments):
        rise = heights[i + 1] - heights[i] if heights else 0.0
        mean = (heights[i + 1] + heights[i]) / 2 if heights else 0.0
        seg.update(rise_m=rise, elevation_m=mean)
    return 'available' if heights else 'unavailable'


def get_road_routes(source, destination):
    start, end = coordinates(source), coordinates(destination)
    if start == end:
        raise ValueError('Origin and destination must be different.')
    base = os.environ.get('OSRM_BASE_URL', 'https://router.project-osrm.org').rstrip('/')
    path = f'{start[1]},{start[0]};{end[1]},{end[0]}'
    try:
        response = requests.get(f'{base}/route/v1/driving/{path}', params={
            'alternatives': 'true', 'overview': 'full', 'geometries': 'geojson',
            'annotations': 'distance,duration', 'steps': 'true',
        }, timeout=(5, 20))
        response.raise_for_status()
        data = response.json()
        if data.get('code') != 'Ok' or not data.get('routes'):
            raise ProviderUnavailable('No drivable route returned. Try different locations.')
        result = []
        for route in data['routes'][:3]:
            distance = float(route['distance']) / 1000
            duration = float(route['duration']) / 60
            points = [[float(lat), float(lng)] for lng, lat in route['geometry']['coordinates']]
            if not (math.isfinite(distance) and math.isfinite(duration) and distance > 0 and duration > 0 and len(points) >= 2):
                raise ValueError('Invalid provider route')
            leg = route['legs'][0]
            distances = [float(x) for x in leg['annotation']['distance']]
            durations = [float(x) for x in leg['annotation']['duration']]
            if len(distances) != len(points) - 1 or len(durations) != len(distances):
                raise ValueError('Annotation does not match geometry')
            segments = _segments(points, distances, durations)
            turns = sum(1 for step in leg['steps'] if step['maneuver']['type'] in SLOWDOWN_MANEUVERS)
            result.append({'distance_km': distance, 'duration_min': duration,
                           'pathPoints': _thin(points, MAX_PATH_POINTS), 'segments': segments,
                           'turns': turns, 'elevation_status': _with_elevation(segments)})
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
        raise ProviderUnavailable('Routing service unavailable. Nothing was saved; please retry.') from exc
