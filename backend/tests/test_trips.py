def test_start_trip_not_found(client, admin_headers):
    res = client.post('/api/v1/trips/999/start', headers=admin_headers)
    assert res.status_code == 404

def test_end_trip_not_found(client, admin_headers):
    res = client.post('/api/v1/trips/999/end', headers=admin_headers, json={})
    assert res.status_code == 404
