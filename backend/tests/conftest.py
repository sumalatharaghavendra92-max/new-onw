import pytest
from app import create_app, db
from app.models import User, UserRole

@pytest.fixture
def app():
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'JWT_SECRET_KEY': 'test-only-secret-at-least-32-characters',
        'SECRET_KEY': 'test-secret',
        'RATELIMIT_ENABLED': False
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def admin_headers(app, client):
    # Create admin user
    user = User(email="testadmin@gogreen.com", phone="1234567890", name="Admin", role=UserRole.admin, password_hash="hash")
    db.session.add(user)
    db.session.commit()
    
    from flask_jwt_extended import create_access_token
    token = create_access_token(identity=str(user.id))
    return {"Authorization": f"Bearer {token}"}
