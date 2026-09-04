from flask import Blueprint, current_app, jsonify, render_template
from pymongo.errors import PyMongoError

main = Blueprint("main", __name__)


@main.get("/")
def home():
    return render_template("index.html", screen="welcome")


@main.get("/entrar")
def login():
    return render_template("index.html", screen="login")


@main.get("/mapa")
def map_view():
    return render_template("index.html", screen="map")


@main.get("/local")
def place():
    return render_template("index.html", screen="place")


@main.get("/perfil")
def profile():
    return render_template("index.html", screen="profile")


@main.get("/health")
def health():
    try:
        current_app.extensions["mongo_client"].admin.command("ping")
    except PyMongoError:
        return jsonify(status="indisponivel", database="mongo"), 503

    return jsonify(status="ok", database="mongo")
