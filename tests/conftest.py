"""Pytest configuration and shared fixtures."""
import pytest
from app import create_app, db as _db
from app.models import User
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    _app = create_app("testing")
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def seed_user(app):
    """Create a base test user."""
    with app.app_context():
        existing = User.query.filter_by(national_id="1199000000000001").first()
        if not existing:
            user = User(
                national_id   = "1199000000000001",
                email         = "fixture@govca.rw",
                password_hash = generate_password_hash("FixturePass99"),
                full_name     = "Fixture User",
            )
            _db.session.add(user)
            _db.session.commit()
            return user
        return existing
