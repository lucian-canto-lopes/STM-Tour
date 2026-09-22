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

community = Blueprint('community', __name__)
community.before_request(protect_forms)


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
    return render_template('community/places.html', places=public_places())


@community.get('/locais/<place_id>')
def detail(place_id):
    place = public_place(place_id)
    photos = list(db().contributions.find({'place_id': place['_id'], 'kind': 'photo', 'status': 'approved'}, {'photo': 0}))
    return render_template('community/detail.html', place=place, photos=photos)


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
            db().contributions.insert_one(data)
            flash('Contribuição enviada para aprovação.')
            return redirect(url_for('community.mine'))
        except ValueError as exc:
            error = str(exc)
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
