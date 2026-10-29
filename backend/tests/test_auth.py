def test_login_success(client, app, monkeypatch):
    sent = []
    monkeypatch.setattr("app.blueprints.auth.routes.send_otp", lambda email, code: sent.append(code))
    # We will mock the user login
    from app import db
    import bcrypt
    from app.models import User, UserRole
    
    with app.app_context():
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw("Pass123!".encode('utf-8'), salt).decode('utf-8')
        user = User(email="test@gogreen.com", phone="0987654321", password_hash=hashed, name="Test User", role=UserRole.admin)
        db.session.add(user)
        db.session.commit()
        
    res = client.post('/api/v1/auth/login', json={"email": "test@gogreen.com", "password": "Pass123!"})
    assert res.status_code == 200
    assert res.json['otp_required'] is True
    assert 'access_token' not in res.json
    res = client.post('/api/v1/auth/login', json={"email": "test@gogreen.com", "password": "Pass123!", "otp": sent[0]})
    assert res.status_code == 200
    assert 'access_token' in res.json
    
def test_login_invalid(client):
    res = client.post('/api/v1/auth/login', json={"email": "test@gogreen.com", "password": "wrong"})
    assert res.status_code == 401
