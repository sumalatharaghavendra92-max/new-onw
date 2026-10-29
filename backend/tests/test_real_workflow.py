import time
import bcrypt
from app import db
from app.models import EmailOTP, User, UserRole, FleetReading, Vehicle


def test_registration_delivery_failure_never_claims_sent(client, monkeypatch):
    def fail(*args):
        raise RuntimeError('provider unavailable')
    monkeypatch.setattr('app.blueprints.auth.routes.send_otp', fail)
    response = client.post('/api/v1/auth/request-otp', json={'email': 'driver@example.com'})
    assert response.status_code == 503
    assert EmailOTP.query.count() == 0
    assert 'demo_otp' not in response.json


def test_registration_real_delivery_contract_and_replay(client, monkeypatch):
    sent = []
    monkeypatch.setattr('app.blueprints.auth.routes.send_otp', lambda email, code: sent.append((email, code)))
    result = client.post('/api/v1/auth/request-otp', json={'email': 'new@example.com'})
    assert result.status_code == 200 and len(sent) == 1
    assert sent[0][1] not in result.get_data(as_text=True)
    record = EmailOTP.query.one()
    assert record.code_hash != sent[0][1]
    assert client.post('/api/v1/auth/request-otp', json={'email': 'new@example.com'}).status_code == 429
    details = dict(email='new@example.com', otp=sent[0][1], name='My driver', phone='+919876543210', password='PersonalPass123!', license_no='MY-LICENSE')
    assert client.post('/api/v1/auth/verify-otp', json=details).status_code == 200
    assert client.post('/api/v1/auth/register', json=details).status_code == 201
    assert client.post('/api/v1/auth/register', json=details).status_code == 400
    assert client.post('/api/v1/auth/login', json=details).status_code == 403  # pending approval


def test_otp_attempt_limit_and_expiry(client, monkeypatch):
    sent = []
    monkeypatch.setattr('app.blueprints.auth.routes.send_otp', lambda email, code: sent.append(code))
    client.post('/api/v1/auth/request-otp', json={'email': 'new@example.com'})
    wrong = '000000' if sent[0] != '000000' else '111111'
    for _ in range(5):
        assert client.post('/api/v1/auth/verify-otp', json={'email': 'new@example.com', 'otp': wrong}).status_code == 400
    assert client.post('/api/v1/auth/verify-otp', json={'email': 'new@example.com', 'otp': sent[0]}).status_code == 400
    record = EmailOTP.query.one()
    record.attempts = 0
    record.expires_at = time.time() - 1
    db.session.commit()
    assert client.post('/api/v1/auth/verify-otp', json={'email': 'new@example.com', 'otp': sent[0]}).status_code == 400


def test_login_requires_second_factor_and_consumes_it(client, monkeypatch):
    sent = []
    monkeypatch.setattr('app.blueprints.auth.routes.send_otp', lambda email, code: sent.append(code))
    db.session.add(User(email='owner@example.com', name='Owner', phone='12345', role=UserRole.admin,
                        password_hash=bcrypt.hashpw(b'PersonalPass123!', bcrypt.gensalt()).decode()))
    db.session.commit()
    details = dict(email='owner@example.com', password='PersonalPass123!')
    response = client.post('/api/v1/auth/login', json=details)
    assert response.json['otp_required'] and 'access_token' not in response.json
    assert client.post('/api/v1/auth/verify-otp', json={'email': details['email'], 'otp': sent[0]}).status_code == 400
    response = client.post('/api/v1/auth/login', json={**details, 'otp': sent[0]})
    assert response.status_code == 200 and response.json['access_token']
    assert client.post('/api/v1/auth/login', json={**details, 'otp': sent[0]}).status_code == 400


def test_sample_import_repeatable_and_manual_readings(app, client, admin_headers):
    runner = app.test_cli_runner()
    for _ in range(2):
        result = runner.invoke(args=['import-sample-fleet'])
        assert result.exit_code == 0, result.output
    assert Vehicle.query.count() == 25 and FleetReading.query.count() == 25
    rows = client.get('/api/v1/vehicles', headers=admin_headers).json
    assert len({x['reading']['fuel_percent'] for x in rows}) == 25
    assert all(x['reading']['source'] == 'sample' and x['reading']['recorded_at'] is None for x in rows)
    assert client.get('/api/v1/admin/fleet', headers=admin_headers).json == {'trips': [], 'rounds': []}
    path = f"/api/v1/vehicles/{rows[0]['id']}/reading"
    assert client.put(path, json={}).status_code == 401
    for invalid in [dict(fuel_percent=101, load_kg=100, odometer_km=5), dict(fuel_percent=50, load_kg=999999, odometer_km=5)]:
        assert client.put(path, headers=admin_headers, json=invalid).status_code == 422
    response = client.put(path, headers=admin_headers, json=dict(fuel_percent=51, load_kg=400, odometer_km=13000))
    assert response.status_code == 200 and response.json['source'] == 'manual' and response.json['recorded_at']


def test_create_personal_admin(app):
    result = app.test_cli_runner().invoke(args=['create-admin', '--email', 'mine@example.com', '--name', 'My Name', '--phone', '9999000011'], input='MyPrivatePass123!\nMyPrivatePass123!\n')
    assert result.exit_code == 0, result.output
    assert User.query.filter_by(email='mine@example.com').one().role == UserRole.admin


def test_smtp_uses_verified_tls_and_actual_email_message(monkeypatch):
    from app.services import email_delivery
    sent = []
    for key, value in {'EMAIL_PROVIDER': 'smtp', 'EMAIL_FROM': 'sender@example.com', 'SMTP_HOST': 'smtp.example.com', 'SMTP_PORT': '465', 'SMTP_USERNAME': 'sender@example.com', 'SMTP_PASSWORD': 'test-only-not-a-credential'}.items():
        monkeypatch.setenv(key, value)
    class SMTP:
        def __init__(self, host, port, context, timeout):
            import ssl
            assert host == 'smtp.example.com' and port == 465
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def login(self, username, password):
            assert username == 'sender@example.com' and password == 'test-only-not-a-credential'
        def send_message(self, message):
            sent.append(message)
    monkeypatch.setattr(email_delivery.smtplib, 'SMTP_SSL', SMTP)
    email_delivery.send_otp('recipient@example.com', '123456')
    assert sent[0]['To'] == 'recipient@example.com'
    assert '123456' in sent[0].get_content()


def test_resend_uses_provider_api_and_checks_response(monkeypatch):
    from app.services import email_delivery
    for key, value in {'EMAIL_PROVIDER': 'resend', 'EMAIL_FROM': 'sender@example.com', 'RESEND_API_KEY': 'test-only-not-a-credential'}.items():
        monkeypatch.setenv(key, value)
    calls = []
    class Response:
        def raise_for_status(self):
            calls.append('checked')
    def post(url, headers, json, timeout):
        assert url == 'https://api.resend.com/emails' and timeout == 20
        assert headers['Authorization'] == 'Bearer test-only-not-a-credential'
        assert json['to'] == ['recipient@example.com'] and '123456' in json['text']
        return Response()
    monkeypatch.setattr(email_delivery.requests, 'post', post)
    email_delivery.send_otp('recipient@example.com', '123456')
    assert calls == ['checked']
