"""Contribuições só são publicadas após uma decisão administrativa."""
import io
from datetime import datetime, timezone
from functools import wraps

from bson import ObjectId
from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from pymongo.errors import PyMongoError

from app.admin import db, login_required, protect_forms, read_photo
from app.auth import current_user, is_admin
from app.location import coordinates
from app.place_filters import read_category, save_category

community = Blueprint('community', __name__)
community.before_request(protect_forms)


@community.app_context_processor
def template_helpers():
    return {'current_user': current_user}


def signed_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for('main.login'))
        return view(*args, **kwargs)
    return wrapped


def identity():
    from flask import session
    return {'author_id': current_user()['_id'], 'author_source': session.get('account_source', 'users')}


def favorite_identity():
    from flask import session
    return {'user_id': current_user()['_id'], 'user_source': session.get('account_source', 'users')}


def favorite_collection():
    collection = db().favorites
    collection.create_index(
        [('user_id', 1), ('user_source', 1), ('place_id', 1)],
        unique=True,
    )
    return collection


def favorite_ids():
    return {item['place_id'] for item in favorite_collection().find(favorite_identity(), {'place_id': 1})}


def object_id(value):
    if not ObjectId.is_valid(value):
        abort(404)
    return ObjectId(value)


def public_places():
    places = list(db().places.find({}, {'photo': 0}))
    places.extend(db().contributions.find({'kind': 'new', 'status': 'approved'}, {'photo': 0}))
    return places


def public_place(place_id):
    key = object_id(place_id)
    place = db().places.find_one({'_id': key}, {'photo': 0})
    if place is None:
        place = db().contributions.find_one({'_id': key, 'kind': 'new', 'status': 'approved'}, {'photo': 0})
    if place is None:
        abort(404)
    latest = db().contributions.find_one({'place_id': key, 'kind': 'description', 'status': 'approved'}, {'description': 1}, sort=[('reviewed_at', -1), ('_id', -1)])
    if latest:
        place['description'] = latest['description']
    return place


@community.errorhandler(PyMongoError)
def database_error(error):
    return render_template('community/message.html', message='Serviço indisponível. Tente novamente em instantes.'), 503


@community.errorhandler(413)
def upload_error(error):
    return render_template('community/message.html', message='O envio excede o limite. Envie uma foto de até 5 MB.'), 413


@community.get('/locais')
def places():
    favorites = favorite_ids() if current_user() else set()
    places = public_places()
    for place in places:
        place['is_favorite'] = place['_id'] in favorites
    return render_template('community/places.html', places=places)


@community.get('/favoritos')
@signed_in
def favorites():
    saved = list(favorite_collection().find(favorite_identity(), {'place_id': 1}).sort('created_at', -1))
    public = {str(place['_id']): place for place in public_places()}
    places = [public[str(item['place_id'])] for item in saved if str(item['place_id']) in public]
    for place in places:
        place['is_favorite'] = True
    return render_template('community/favorites.html', places=places)


@community.post('/locais/<place_id>/favoritar')
@signed_in
def toggle_favorite(place_id):
    place = public_place(place_id)
    target = {**favorite_identity(), 'place_id': place['_id']}
    favorites = favorite_collection()
    if favorites.find_one(target):
        favorites.delete_one(target)
        flash('Local removido dos favoritos.')
    else:
        from datetime import datetime, timezone
        favorites.insert_one({**target, 'created_at': datetime.now(timezone.utc)})
        flash('Local adicionado aos favoritos.')
    return_to = request.form.get('return_to')
    if return_to == 'favorites':
        destination = url_for('community.favorites')
    elif return_to == 'places':
        destination = url_for('community.places')
    else:
        destination = url_for('community.detail', place_id=place_id)
    return redirect(destination)


def render_detail(place, error=None, values=None, photo_error=None):
    photos = list(db().contributions.find({'place_id': place['_id'], 'kind': 'photo', 'status': 'approved'}, {'photo': 0}))
    user = current_user()
    place['is_favorite'] = bool(user and place['_id'] in favorite_ids())
    reviews = list(db().place_reviews.find({'place_id': place['_id']}).sort('updated_at', -1))
    own_review = next((item for item in reviews if user and
                       item.get('author_id') == user['_id'] and
                       item.get('author_source') == identity()['author_source']), None)
    average = round(sum(item['rating'] for item in reviews) / len(reviews), 1) if reviews else None
    return render_template('community/detail.html', place=place, photos=photos,
                           reviews=reviews, average=average, own_review=own_review,
                           review_values=values if values is not None else (own_review or {}),
                           review_error=error, photo_error=photo_error), 400 if error or photo_error else 200


@community.get('/locais/<place_id>')
def detail(place_id):
    return render_detail(public_place(place_id))


@community.post('/locais/<place_id>/avaliar')
@signed_in
def rate_place(place_id):
    place = public_place(place_id)
    try:
        rating = float(request.form.get('rating', '').replace(',', '.'))
        if rating not in [step / 2 for step in range(1, 11)]:
            raise ValueError
    except ValueError:
        return render_detail(place, 'Escolha uma avaliação de 0,5 a 5 estrelas, em passos de meia estrela.', request.form)
    comment = request.form.get('comment', '').strip()
    if len(comment) > 2000:
        return render_detail(place, 'O comentário deve ter até 2.000 caracteres.', request.form)
    collection = db().place_reviews
    collection.create_index([('place_id', 1), ('author_id', 1), ('author_source', 1)], unique=True)
    collection.update_one({'place_id': place['_id'], **identity()}, {'$set': {
        'rating': rating, 'comment': comment,
        'author_name': current_user().get('name') or 'Explorador',
        'updated_at': datetime.now(timezone.utc),
    }}, upsert=True)
    flash('Avaliação salva. Obrigado por compartilhar sua experiência!')
    return redirect(url_for('community.detail', place_id=place_id, _anchor='avaliacoes'))


@community.get('/locais/<place_id>/foto')
def place_photo(place_id):
    place = public_place(place_id)
    item = db().places.find_one({'_id': place['_id']}, {'photo': 1})
    if item is None:
        item = db().contributions.find_one({'_id': place['_id'], 'status': 'approved'}, {'photo': 1})
    if not item or not item.get('photo'):
        abort(404)
    return send_file(io.BytesIO(item['photo']), mimetype='image/jpeg', max_age=0)


@community.route('/contribuir', methods=['GET', 'POST'])
@community.route('/locais/<place_id>/contribuir', methods=['GET', 'POST'])
@signed_in
def submit(place_id=None):
    place = public_place(place_id) if place_id else None
    error = None
    if request.method == 'POST':
        try:
            kind = request.form.get('kind') if place else 'new'
            if kind not in (('photo', 'description') if place else ('new',)):
                raise ValueError('Selecione uma contribuição válida.')
            data = {**identity(), 'kind': kind, 'status': 'pending', 'created_at': datetime.now(timezone.utc)}
            if place:
                data.update(place_id=place['_id'], name=place['name'])
            else:
                data['name'] = request.form.get('name', '').strip()
                if not data['name'] or len(data['name']) > 120:
                    raise ValueError('Informe um nome com até 120 caracteres.')
            if kind == 'new':
                data['category'] = read_category(request.form)
                data.update(coordinates(request.form))
            if kind in ('new', 'description'):
                data['description'] = request.form.get('description', '').strip()
                if not data['description'] or len(data['description']) > 5000:
                    raise ValueError('Informe uma descrição com até 5.000 caracteres.')
            if kind in ('new', 'photo'):
                upload = request.files.get('photo')
                if not upload or not upload.filename:
                    raise ValueError('Selecione uma foto.')
                data['photo'] = read_photo(upload)
            if kind == 'new':
                save_category(request.form, data['category'])
            db().contributions.insert_one(data)
            flash('Contribuição enviada para aprovação.')
            if place and request.form.get('return_to') == 'detail':
                return redirect(url_for('community.detail', place_id=place_id, _anchor='fotos'))
            return redirect(url_for('community.mine'))
        except ValueError as exc:
            error = str(exc)
            if place and request.form.get('return_to') == 'detail' and request.form.get('kind') == 'photo':
                return render_detail(place, photo_error=error)
    return render_template('community/submit.html', place=place, error=error, values=request.form), 400 if error else 200


@community.get('/minhas-contribuicoes')
@signed_in
def mine():
    items = list(db().contributions.find(identity(), {'photo': 0}).sort('created_at', -1))
    return render_template('community/reviews.html', items=items, moderation=False)


@community.get('/contribuicoes/<contribution_id>/foto')
def contribution_photo(contribution_id):
    item = db().contributions.find_one({'_id': object_id(contribution_id)})
    if not item or not item.get('photo'):
        abort(404)
    if item['status'] != 'approved':
        user = current_user()
        if not user or (not is_admin(user) and any(item.get(k) != v for k, v in identity().items())):
            abort(404)
    elif item.get('place_id'):
        public_place(str(item['place_id']))
    return send_file(io.BytesIO(item['photo']), mimetype='image/jpeg', max_age=0)


@community.get('/admin/contribuicoes')
@login_required
def review_queue():
    items = list(db().contributions.find({'status': 'pending'}, {'photo': 0}).sort('created_at', 1))
    for item in items:
        if item.get('place_id'):
            # Inclui a descrição atual para comparação, sem expor conteúdo pendente.
            key = item['place_id']
            exists = db().places.find_one({'_id': key}, {'_id': 1}) or db().contributions.find_one({'_id': key, 'kind': 'new', 'status': 'approved'}, {'_id': 1})
            item['current'] = public_place(str(key)) if exists else None
    return render_template('community/reviews.html', items=items, moderation=True)


@community.post('/admin/contribuicoes/<contribution_id>/revisar')
@login_required
def review(contribution_id):
    key = object_id(contribution_id)
    decision = request.form.get('decision')
    if decision not in ('approved', 'rejected'):
        abort(400)
    item = db().contributions.find_one({'_id': key})
    if not item:
        abort(404)
    if decision == 'approved' and item.get('place_id'):
        public_place(str(item['place_id']))
    result = db().contributions.update_one({'_id': key, 'status': 'pending'}, {'$set': {
        'status': decision, 'reviewed_at': datetime.now(timezone.utc),
        'reviewer': identity(),
    }})
    if not result.modified_count:
        abort(409, description='Esta contribuição já foi revisada.')
    flash('Contribuição aprovada e publicada.' if decision == 'approved' else 'Contribuição rejeitada.')
    return redirect(url_for('community.review_queue'))
