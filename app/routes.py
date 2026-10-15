import io

import folium
from branca.element import MacroElement, Template
from app.location import coordinates
from app.place_filters import map_places

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, session, url_for, flash
from pymongo.errors import PyMongoError, DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash
from app.admin import protect_forms, read_photo
from app.auth import current_user, is_admin

main = Blueprint("main", __name__)


@main.get("/")
def home():
    return render_template("index.html", screen="welcome")


@main.get("/mapa/conteudo")
def map_embed():
    city_map = folium.Map(
        location=[-2.4431, -54.7083],
        zoom_start=13,
        tiles="OPNVKarte",
        control_scale=True,
        zoom_control=True,
        scrollWheelZoom=True,
    )
    bounds = []
    for entry in map_places(request.args.get("q", "").strip(), request.args.get("category", "")):
        try:
            location = coordinates(entry)
        except ValueError:
            continue
        place = entry
        point = [location['latitude'], location['longitude']]
        card = render_template('partials/map_card.html', place=place)
        popup = folium.Popup(folium.IFrame(html=card, width=250, height=270), max_width=270)
        folium.Marker(point, popup=popup).add_to(city_map)
        bounds.append(point)
    if bounds:
        city_map.fit_bounds(bounds, max_zoom=15, padding=(25, 25))
    return city_map.get_root().render()


@main.get("/mapa/selecionar")
def location_picker():
    picker = folium.Map(location=[-2.4431, -54.7083], zoom_start=13, tiles="OPNVKarte")
    handler = MacroElement()
    handler._template = Template("""
        {% macro script(this, kwargs) %}
        const pickerMap = {{ this._parent.get_name() }};
        let chosenMarker;
        function choosePoint(lat, lng, notify) {
            if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return;
            if (!chosenMarker) {
                chosenMarker = L.marker([lat, lng], {draggable: true}).addTo(pickerMap);
                chosenMarker.on('dragend', function() {
                    const point = chosenMarker.getLatLng().wrap();
                    choosePoint(point.lat, point.lng, true);
                });
            } else chosenMarker.setLatLng([lat, lng]);
            if (notify) window.parent.postMessage({type: 'location-selected', latitude: lat, longitude: lng}, window.location.origin);
            else pickerMap.setView([lat, lng], 15);
        }
        pickerMap.on('click', function(event) {
            const point = event.latlng.wrap();
            choosePoint(point.lat, point.lng, true);
        });
        window.addEventListener('message', function(event) {
            if (event.origin !== window.location.origin || event.source !== window.parent || event.data?.type !== 'location-set') return;
            choosePoint(event.data.latitude, event.data.longitude, false);
        });
        window.parent.postMessage({type: 'location-ready'}, window.location.origin);
        {% endmacro %}
    """)
    picker.add_child(handler)
    return picker.get_root().render()


@main.before_request
def validate_forms():
    protect_forms()


@main.errorhandler(PyMongoError)
def database_error(error):
    return render_template("user_auth.html", register=False, error="Serviço indisponível. Tente novamente em instantes."), 503


@main.route("/entrar", methods=["GET", "POST"])
def login():
    account = current_user()
    if account:
        return redirect(url_for("admin.index" if is_admin(account) else "main.map_view"))
    if request.method == "POST":
        database = current_app.extensions["mongo_db"]
        email = request.form.get("email", "").strip().lower()
        source = "users"
        user = database.users.find_one({"email": email})
        if user is None:
            source = "admins"
            user = database.admins.find_one({"email": email})
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user_id=str(user["_id"]), user_name=user.get("name") or user["email"], account_source=source)
            session.permanent = True
            return redirect(url_for("admin.index" if source == "admins" or is_admin(user) else "main.map_view"))
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
        if current_app.extensions["mongo_db"].admins.find_one({"email": email}):
            return render_template("user_auth.html", register=True, error="Já existe uma conta com esse e-mail."), 400
        users.create_index("email", unique=True)
        try:
            users.insert_one({"name": name, "email": email, "password_hash": generate_password_hash(password), "role": "user"})
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
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    from app.place_filters import categories
    if category not in categories():
        category = ""
    return render_template("index.html", screen="map", query=query, category=category, result_count=len(map_places(query, category)))


@main.get("/local")
def place():
    return redirect(url_for("community.places"))


@main.get("/perfil")
def profile():
    user = current_user()
    if not user:
        return redirect(url_for("main.login"))
    database = current_app.extensions["mongo_db"]
    author = {"author_id": user['_id'], "author_source": session.get('account_source', 'users')}
    reviews = list(database.place_reviews.find(author).sort('updated_at', -1))
    place_ids = [review['place_id'] for review in reviews]
    places = {place['_id']: place for place in database.places.find(
        {'_id': {'$in': place_ids}}, {'name': 1})}
    places.update({place['_id']: place for place in database.contributions.find(
        {'_id': {'$in': place_ids}, 'kind': 'new', 'status': 'approved'}, {'name': 1})})
    for review in reviews:
        review['place'] = places.get(review['place_id'])
    stats = {
        'contributions': database.contributions.count_documents(author),
        'reviews': len(reviews),
        'photos': database.contributions.count_documents({
            **author, 'kind': {'$in': ['new', 'photo']}, 'photo': {'$exists': True},
        }),
    }
    return render_template("index.html", screen="profile", can_admin=is_admin(user),
                           profile_name=user.get('name') or user.get('email') or 'Explorador',
                           profile_bio=user.get('bio', ''),
                           has_profile_photo=bool(user.get('profile_photo')),
                           stats=stats, reviews=reviews)


def account_collection():
    source = session.get('account_source', 'users')
    return current_app.extensions['mongo_db'].admins if source == 'admins' else current_app.extensions['mongo_db'].users


def render_profile_editor(user, error=None, status=200, values=None):
    if values is None:
        values = request.form if request.method == 'POST' else user
    return render_template('profile_edit.html', user=user, values=values, error=error), status


@main.route('/perfil/editar', methods=['GET', 'POST'])
def edit_profile():
    user = current_user()
    if not user:
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            bio = request.form.get('bio', '').strip()
            if not name or len(name) > 120:
                raise ValueError('Informe um nome com até 120 caracteres.')
            if len(bio) > 150:
                raise ValueError('A bio deve ter até 150 caracteres.')
            changes = {'name': name, 'bio': bio}
            upload = request.files.get('photo')
            if upload and upload.filename:
                changes['profile_photo'] = read_photo(upload)
            account_collection().update_one({'_id': user['_id']}, {'$set': changes})
            current_app.extensions['mongo_db'].place_reviews.update_many({
                'author_id': user['_id'],
                'author_source': session.get('account_source', 'users'),
            }, {'$set': {'author_name': name}})
            session['user_name'] = name
            flash('Perfil atualizado com sucesso.')
            return redirect(url_for('main.profile'))
        except ValueError as error:
            return render_profile_editor(user, str(error), 400)
    return render_profile_editor(user)


@main.get('/perfil/foto')
def profile_photo():
    user = current_user()
    if not user:
        return redirect(url_for('main.login'))
    if not user.get('profile_photo'):
        abort(404)
    return send_file(io.BytesIO(user['profile_photo']), mimetype='image/jpeg', max_age=0)


@main.errorhandler(413)
def upload_too_large(error):
    if request.endpoint == 'main.edit_profile' and current_user():
        user = current_user()
        return render_profile_editor(user, 'A foto deve ter no máximo 5 MB.', 413, user)
    return error


@main.get("/health")
def health():
    try:
        current_app.extensions["mongo_client"].admin.command("ping")
    except PyMongoError:
        return jsonify(status="indisponivel", database="mongo"), 503

    return jsonify(status="ok", database="mongo")
