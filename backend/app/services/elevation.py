"""Terrain elevation from the Open-Meteo Elevation API (Copernicus DEM, 90 m)."""
from collections import OrderedDict
import math
import threading

import requests

URL = 'https://api.open-meteo.com/v1/elevation'
BATCH = 100
_cache = OrderedDict()
_lock = threading.Lock()


def _key(lat, lng):
    return round(lat, 4), round(lng, 4)


def get_elevations(points):
    """Elevation in metres for each [lat, lng], or None if the provider fails.

    Callers must treat None as 'terrain unknown' and say so, never as flat ground.
    """
    keys = [_key(float(lat), float(lng)) for lat, lng in points]
    with _lock:
        missing = list(dict.fromkeys(k for k in keys if k not in _cache))
    try:
        for start in range(0, len(missing), BATCH):
            chunk = missing[start:start + BATCH]
            response = requests.get(URL, params={
                'latitude': ','.join(str(lat) for lat, _ in chunk),
                'longitude': ','.join(str(lng) for _, lng in chunk),
            }, timeout=(3, 8))
            response.raise_for_status()
            values = response.json()['elevation']
            if len(values) != len(chunk) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
                raise ValueError('Invalid elevation response')
            with _lock:
                for key, value in zip(chunk, values):
                    _cache[key] = float(value)
                while len(_cache) > 20000:
                    _cache.popitem(last=False)
        with _lock:
            return [_cache[k] for k in keys]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None
