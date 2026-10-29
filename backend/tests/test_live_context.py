from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
import requests
from app.services import live_context as live


@pytest.fixture(autouse=True)
def clear_weather_cache():
    live._cache.clear()
    yield
    live._cache.clear()


def provider_response():
    return Mock(json=lambda: {'current': {
        'time': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        'temperature_2m': 25, 'precipitation': 0, 'wind_speed_10m': 12, 'weather_code': 1}})


@pytest.mark.parametrize('lat,lon', [('nan', 0), (0, 'inf'), (91, 0), (0, -181), (None, 0)])
def test_reject_coordinates_without_network(monkeypatch, lat, lon):
    get = Mock()
    monkeypatch.setattr(live.requests, 'get', get)
    with pytest.raises(ValueError):
        live.get_live_context(lat, lon)
    get.assert_not_called()


def test_cache_and_honest_provenance(monkeypatch):
    get = Mock(return_value=provider_response())
    monkeypatch.setattr(live.requests, 'get', get)
    first = live.get_live_context(12.97, 77.59)
    second = live.get_live_context(12.97, 77.59)
    assert first['status'] == 'available' and not first['cached']
    assert second['cached'] and get.call_count == 1
    assert first['used_in_fuel_prediction'] is False
    assert first['live_traffic_available'] is False
    assert first['valid_at'].endswith('+00:00')
    first['current']['temperature_2m'] = 999
    assert second['current']['temperature_2m'] == 25


def test_stale_fallback_and_expiry(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(live.time, 'monotonic', lambda: clock[0])
    get = Mock(return_value=provider_response())
    monkeypatch.setattr(live.requests, 'get', get)
    live.get_live_context(12, 77)
    get.side_effect = requests.Timeout()
    clock[0] += 601
    fallback = live.get_live_context(12, 77)
    assert fallback['status'] == 'stale' and fallback['current']['temperature_2m'] == 25
    clock[0] += 3600
    assert live.get_live_context(12, 77)['current'] is None


def test_invalid_payload_never_becomes_weather(monkeypatch):
    monkeypatch.setattr(live.requests, 'get', Mock(return_value=Mock(json=lambda: {'current': {}})))
    result = live.get_live_context(12, 77)
    assert result['status'] == 'unavailable' and result['current'] is None


def test_weather_requires_login(client):
    assert client.get('/api/v1/context/weather?latitude=12&longitude=77').status_code == 401


def test_weather_validates_inputs(client, admin_headers):
    assert client.get('/api/v1/context/weather?latitude=nan&longitude=77', headers=admin_headers).status_code == 422
