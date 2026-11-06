import mongomock
import pytest
from werkzeug.security import check_password_hash

from app import create_app


@pytest.fixture
def environment(monkeypatch):
    client = mongomock.MongoClient()
    monkeypatch.setattr('app.MongoClient', lambda *args, **kwargs: client)
    monkeypatch.setenv('MONGO_URI', 'mongodb://localhost/stm_tour')
    monkeypatch.delenv('INITIAL_ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('INITIAL_ADMIN_PASSWORD', raising=False)
    return client.stm_tour


def configure(monkeypatch):
    monkeypatch.setenv('INITIAL_ADMIN_EMAIL', ' ADMIN@example.com ')
    monkeypatch.setenv('INITIAL_ADMIN_PASSWORD', 'initial-secret-123')


def test_no_variables_creates_no_account(environment):
    create_app()
    assert environment.users.count_documents({}) == 0


def test_creates_admin_and_preserves_password_on_restart(environment, monkeypatch):
    configure(monkeypatch)
    create_app()
    account = environment.users.find_one()
    assert account['email'] == 'admin@example.com'
    assert account['role'] == 'admin'
    assert check_password_hash(account['password_hash'], 'initial-secret-123')
    assert 'password' not in account
    monkeypatch.setenv('INITIAL_ADMIN_PASSWORD', 'different-secret-123')
    create_app()
    assert list(environment.users.find()) == [account]


@pytest.mark.parametrize('collection', ['users', 'admins'])
def test_existing_accounts_are_never_changed(environment, monkeypatch, collection):
    configure(monkeypatch)
    existing = {'email': 'admin@example.com', 'role': 'user', 'password_hash': 'preserved'}
    environment[collection].insert_one(existing)
    create_app()
    assert environment[collection].find_one() == existing
    assert environment.users.count_documents({}) == (collection == 'users')


@pytest.mark.parametrize('email,password', [
    ('admin@example.com', ''), ('', 'initial-secret-123'),
    ('invalid', 'initial-secret-123'), ('admin@example.com', 'short'),
])
def test_invalid_configuration_fails_without_creating_account(environment, monkeypatch, email, password):
    monkeypatch.setenv('INITIAL_ADMIN_EMAIL', email)
    monkeypatch.setenv('INITIAL_ADMIN_PASSWORD', password)
    with pytest.raises(ValueError, match='INITIAL_ADMIN_EMAIL'):
        create_app()
    assert environment.users.count_documents({}) == 0
