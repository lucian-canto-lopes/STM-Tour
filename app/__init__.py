import os

from flask import Flask
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "altere-esta-chave-em-producao"),
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://mongo:27017/stm_tour"),
    )

    mongo_client = MongoClient(app.config["MONGO_URI"])
    app.extensions["mongo_client"] = mongo_client
    app.extensions["mongo_db"] = mongo_client.get_database()

    from app.routes import main

    app.register_blueprint(main)

    @app.teardown_appcontext
    def close_mongo_connection(_error=None):
        # O cliente é compartilhado pelo processo e gerencia seu próprio pool.
        return None

    return app
