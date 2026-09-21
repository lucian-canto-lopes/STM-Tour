import os
import secrets
from datetime import timedelta

from flask import Flask
from pymongo import MongoClient


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://mongo:27017/stm_tour"),
    )

    app.config.update(
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    )

    mongo_client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=5000)
    app.extensions["mongo_client"] = mongo_client
    app.extensions["mongo_db"] = mongo_client.get_database()

    from app.routes import main

    app.register_blueprint(main)

    from app.admin import init_admin
    init_admin(app)

    @app.teardown_appcontext
    def close_mongo_connection(_error=None):
        # O cliente é compartilhado pelo processo e gerencia seu próprio pool.
        return None

    return app
