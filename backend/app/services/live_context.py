"""Public model-derived weather context, never a measured fuel/traffic signal."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import math
import threading
import time

import requests

URL = 'https://api.open-meteo.com/v1/forecast'
TTL_SECONDS = 600
MAX_STALE_SECONDS = 3600
_cache = OrderedDict()
_lock = threading.Lock()


def coordinates(latitude, longitude):
    try:
        lat, lon = float(latitude), float(longitude)
    except (ValueError, TypeError):
        raise ValueError('latitude and longitude must be finite coordinates.')
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('latitude must be -90..90 and longitude -180..180.')
    return round(lat, 3), round(lon, 3)


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def _base(lat, lon):
    return dict(source='Open-Meteo', source_url='https://open-meteo.com/',
                attribution='Weather data by Open-Meteo (CC BY 4.0)',
                requested_location={'latitude': lat, 'longitude': lon},
                data_kind='Weather-model estimate; not a station observation',
                used_in_fuel_prediction=False, live_traffic_available=False,
                refresh_interval_seconds=TTL_SECONDS)


def _view(data, age, cached, failed=False):
    result = deepcopy(data)
    result.update(cache_age_seconds=round(age), cached=cached)
    # A recent HTTP response may still contain old provider data.
    source_age = (datetime.now(timezone.utc) - datetime.fromisoformat(result['valid_at'])).total_seconds()
    stale = failed or age >= TTL_SECONDS or source_age > 1800 or source_age < -900
    result.update(status='stale' if stale else 'available', stale=stale,
                  source_age_seconds=round(source_age))
    if failed:
        result['warning'] = 'Provider unavailable; showing explicitly stale cached weather.'
    return result


def get_live_context(latitude, longitude):
    lat, lon = coordinates(latitude, longitude)
    key, now = (lat, lon), time.monotonic()
    with _lock:
        entry = _cache.get(key)
    if entry and now - entry[0] < TTL_SECONDS:
        return _view(entry[1], now - entry[0], True)
    try:
        response = requests.get(URL, params={
            'latitude': lat, 'longitude': lon,
            'current': 'temperature_2m,precipitation,weather_code,wind_speed_10m',
            'timezone': 'GMT', 'wind_speed_unit': 'kmh',
        }, timeout=(3, 8))
        response.raise_for_status()
        payload = response.json()
        current = payload['current']
        valid_at = datetime.fromisoformat(current['time']).replace(tzinfo=timezone.utc)
        values = {name: float(current[name]) for name in
                  ('temperature_2m', 'precipitation', 'weather_code', 'wind_speed_10m')}
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError('Invalid provider values')
        if values['precipitation'] < 0 or values['wind_speed_10m'] < 0:
            raise ValueError('Invalid negative weather values')
        data = _base(lat, lon)
        data.update(valid_at=valid_at.isoformat(), fetched_at=_timestamp(),
                    current=values, units={'temperature_2m': '°C', 'precipitation': 'mm',
                                          'wind_speed_10m': 'km/h', 'weather_code': 'WMO code'})
        with _lock:
            _cache[key] = (time.monotonic(), data)
            _cache.move_to_end(key)
            while len(_cache) > 256:
                _cache.popitem(last=False)
        return _view(data, 0, False)
    except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError):
        age = time.monotonic() - entry[0] if entry else None
        if entry and age <= MAX_STALE_SECONDS:
            return _view(entry[1], age, True, failed=True)
        return dict(_base(lat, lon), status='unavailable', stale=True, current=None,
                    valid_at=None, fetched_at=None, cached=False,
                    warning='Weather provider unavailable. No weather values have been invented.')
