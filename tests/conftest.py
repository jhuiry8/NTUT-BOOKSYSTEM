import os

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

from app import create_app  # noqa: E402
from extensions import db  # noqa: E402


@pytest.fixture
def app():
    application = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
