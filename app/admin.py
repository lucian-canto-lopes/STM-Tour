import hmac
import io
import secrets
from functools import wraps

import click
from bson import ObjectId
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, session, url_for
from PIL import Image, UnidentifiedImageError
from pymongo.errors import PyMongoError
from werkzeug.security import generate_password_hash
from app.auth import current_user, is_admin

admin = Blueprint('admin', __name__, url_prefix='/admin')


def db():
    return current_app.extensions['mongo_db']


def csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


@admin.app_context_processor
def helpers():
    return {'csrf_token': csrf_token}


@admin.before_request
def protect_forms():
    if request.method == 'POST' and (not session.get('csrf_token') or not hmac.compare_digest(session['csrf_token'], request.form.get('csrf_token', ''))):
        abort(400, description='Formulário expirado. Recarregue a página.')


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            session.clear()
            return redirect(url_for('main.login'))
        if not is_admin(user):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@admin.errorhandler(PyMongoError)
def database_error(error):
    return render_template('admin/error.html', message='Banco de dados indisponível. Tente novamente em alguns instantes.'), 503


@admin.errorhandler(413)
def upload_error(error):
    return render_template('admin/error.html', message='A foto deve ter no máximo 5 MB.'), 413


@admin.route('/entrar', methods=['GET', 'POST'])
def login():
    return redirect(url_for('main.login'), code=307 if request.method == 'POST' else 302)


@admin.post('/sair')
def logout():
    session.clear()
    return redirect(url_for('main.login'))


@admin.get('/')
@login_required
def index():
    return render_template('admin/index.html', places=list(db().places.find({}, {'photo': 0}).sort('_id', -1)))


def get_place(place_id, projection=None):
    if not ObjectId.is_valid(place_id):
        abort(404)
    place = db().places.find_one({'_id': ObjectId(place_id)}, projection)
    if not place:
        abort(404)
    return place


def read_photo(upload):
    raw = upload.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError('A foto deve ter no máximo 5 MB.')
    try:
        with Image.open(io.BytesIO(raw)) as photo:
            if photo.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Envie uma foto JPG, PNG ou WebP.')
            if photo.width * photo.height > 20_000_000:
                raise ValueError('A foto deve ter no máximo 20 megapixels.')
            photo.load()
            photo.thumbnail((1600, 1600))
            output = io.BytesIO()
            photo.convert('RGB').save(output, format='JPEG', quality=85)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('O arquivo enviado não é uma imagem válida.') from None


@admin.route('/locais/novo', methods=['GET', 'POST'])
@admin.route('/locais/<place_id>/editar', methods=['GET', 'POST'])
@login_required
def edit(place_id=None):
    place = get_place(place_id, {'photo': 0}) if place_id else None
    values = request.form if request.method == 'POST' else (place or {})
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            if not name or len(name) > 120:
                raise ValueError('Informe um nome com até 120 caracteres.')
            if not description or len(description) > 5000:
                raise ValueError('Informe uma descrição com até 5.000 caracteres.')
            data = {'name': name, 'description': description}
            upload = request.files.get('photo')
            if upload and upload.filename:
                data['photo'] = read_photo(upload)
            elif not place:
                raise ValueError('Selecione uma foto para o local.')
            if place:
                db().places.update_one({'_id': place['_id']}, {'$set': data})
            else:
                db().places.insert_one(data)
            flash('Local salvo com sucesso.', 'success')
            return redirect(url_for('admin.index'))
        except ValueError as error:
            flash(str(error), 'error')
            return render_template('admin/form.html', place=place, values=values), 400
    return render_template('admin/form.html', place=place, values=values)


@admin.get('/locais/<place_id>/foto')
@login_required
def photo(place_id):
    return send_file(io.BytesIO(get_place(place_id)['photo']), mimetype='image/jpeg', max_age=0)


@admin.route('/locais/<place_id>/remover', methods=['GET', 'POST'])
@login_required
def delete(place_id):
    place = get_place(place_id, {'photo': 0})
    if request.method == 'POST':
        db().places.delete_one({'_id': place['_id']})
        flash('Local removido com sucesso.', 'success')
        return redirect(url_for('admin.index'))
    return render_template('admin/delete.html', place=place)


def init_admin(app):
    app.register_blueprint(admin)

    @app.cli.command('create-admin')
    @click.option('--email', prompt='E-mail do administrador')
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, password):
        """Cria um administrador sem senha padrão."""
        email = email.strip().lower()
        if '@' not in email or len(password) < 12:
            raise click.ClickException('Informe um e-mail válido e uma senha com pelo menos 12 caracteres.')
        collection = db().users
        collection.create_index('email', unique=True)
        if collection.find_one({'email': email}) or db().admins.find_one({'email': email}):
            raise click.ClickException('Já existe uma conta com esse e-mail.')
        collection.insert_one({'name': email, 'email': email, 'password_hash': generate_password_hash(password), 'role': 'admin'})
        click.echo('Administrador criado com sucesso.')
