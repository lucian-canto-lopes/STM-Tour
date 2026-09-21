import folium

from flask import Blueprint, current_app, jsonify, redirect, render_template, url_for, request, session, flash
from pymongo.errors import PyMongoError, DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash
from app.admin import protect_forms

main = Blueprint("main", __name__)


@main.get("/")
def home():
    return render_template("index.html", screen="welcome")


@main.get("/mapa/conteudo")
def map_embed():
    city_map = folium.Map(
        location=[-2.4431, -54.7083],
        zoom_start=13,
        tiles="OpenStreetMap",
        control_scale=True,
        zoom_control=True,
        scrollWheelZoom=False,
    )
    return city_map.get_root().render()


@main.before_request
def validate_forms():
    protect_forms()


@main.errorhandler(PyMongoError)
def database_error(error):
    return render_template("user_auth.html", register=False, error="Serviço indisponível. Tente novamente em instantes."), 503


@main.route("/entrar", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("main.map_view"))
    if request.method == "POST":
        user = current_app.extensions["mongo_db"].users.find_one({"email": request.form.get("email", "").strip().lower()})
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=str(user["_id"]), user_name=user["name"])
            session.permanent = True
            return redirect(url_for("main.map_view"))
        return render_template("user_auth.html", register=False, error="E-mail ou senha inválidos."), 401
    return render_template("user_auth.html", register=False)


@main.route("/criar-conta", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 120 or "@" not in email or len(email) > 254 or len(password) < 4:
            return render_template("user_auth.html", register=True, error="Informe nome, e-mail válido e senha com pelo menos 4 caracteres."), 400
        if password != request.form.get("confirmation"):
            return render_template("user_auth.html", register=True, error="As senhas não coincidem."), 400
        users = current_app.extensions["mongo_db"].users
        users.create_index("email", unique=True)
        try:
            users.insert_one({"name": name, "email": email, "password_hash": generate_password_hash(password)})
        except DuplicateKeyError:
            return render_template("user_auth.html", register=True, error="Já existe uma conta com esse e-mail."), 400
        flash("Conta criada. Entre com seu e-mail e senha.")
        return redirect(url_for("main.login"))
    return render_template("user_auth.html", register=True)


@main.post("/sair")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


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
