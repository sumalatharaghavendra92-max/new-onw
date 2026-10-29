def test_get_stats(client, admin_headers):
    res = client.get('/api/v1/admin/stats', headers=admin_headers)
    assert res.status_code == 200
    assert "total_trips" in res.json
    assert "co2_saved_kg" in res.json

def test_get_settings(client, admin_headers):
    res = client.get('/api/v1/admin/settings', headers=admin_headers)
    assert res.status_code == 200
    assert "strict_routing" in res.json

def test_patch_settings(client, admin_headers):
    res = client.patch('/api/v1/admin/settings', headers=admin_headers, json={"strict_routing": False})
    assert res.status_code == 200
    assert res.json['settings']['strict_routing'] == False

def test_backup_restore(client, admin_headers):
    res1 = client.post('/api/v1/admin/backup', headers=admin_headers)
    assert res1.status_code == 200
    
    res2 = client.post('/api/v1/admin/restore', headers=admin_headers)
    assert res1.data.startswith(b"SQLite format 3")
    assert res2.status_code == 501
