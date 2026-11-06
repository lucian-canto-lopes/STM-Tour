import pytest
from pymongo import MongoClient

from app import create_app


@pytest.mark.parametrize('uri, fallback, expected', [
    ('mongodb://localhost:27017/', None, 'stm_tour'),
    ('mongodb://localhost:27017/?authSource=admin', 'production', 'production'),
    ('mongodb://localhost:27017/existing?authSource=admin', 'fallback', 'existing'),
    ('mongodb://localhost:27017/', '', 'stm_tour'),
])
def test_database_selection_without_connecting(monkeypatch, uri, fallback, expected):
    monkeypatch.setenv('MONGO_URI', uri)
    if fallback is None:
        monkeypatch.delenv('MONGO_DB_NAME', raising=False)
    else:
        monkeypatch.setenv('MONGO_DB_NAME', fallback)
    monkeypatch.setattr('app.MongoClient', lambda *args, **kwargs: MongoClient(*args, connect=False, **kwargs))
    app = create_app()
    try:
        assert app.extensions['mongo_db'].name == expected
    finally:
        app.extensions['mongo_client'].close()
