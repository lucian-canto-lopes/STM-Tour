import io

import mongomock
import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True, SECRET_KEY='test-secret')
    app.extensions['mongo_db'] = mongomock.MongoClient().db
    app.extensions['mongo_db'].admins.insert_one({'email': 'admin@example.com', 'password_hash': generate_password_hash('test-password-123')})
    return app.test_client()


def post(client, path, **data):
    with client.session_transaction() as session:
        data['csrf_token'] = session['csrf_token']
    return client.post(path, data=data)


def login(client):
    client.get('/admin/entrar')
    assert post(client, '/admin/entrar', email='admin@example.com', password='test-password-123').status_code == 302
    client.get('/admin/')


def photo(color='green'):
    output = io.BytesIO()
    Image.new('RGB', (20, 20), color).save(output, 'PNG')
    output.seek(0)
    return output, 'photo.png'


def test_access_and_csrf(client):
    for path in ['/admin/', '/admin/locais/novo', '/admin/locais/abc/editar', '/admin/locais/abc/remover', '/admin/locais/abc/foto']:
        assert client.get(path).status_code == 302
    assert client.post('/admin/entrar', data={}).status_code == 400
    client.get('/admin/entrar')
    assert post(client, '/admin/entrar', email='admin@example.com', password='wrong').status_code == 401
    login(client)
    assert client.post('/admin/locais/novo', data={}).status_code == 400
    assert post(client, '/admin/sair').status_code == 302
    assert client.get('/admin/').status_code == 302


def test_place_lifecycle(client):
    login(client)
    assert post(client, '/admin/locais/novo', name='Praia', description='Descrição', photo=photo()).status_code == 302
    collection = client.application.extensions['mongo_db'].places
    place = collection.find_one()
    path = '/admin/locais/' + str(place['_id'])
    assert b'Praia' in client.get('/admin/').data
    response = client.get(path + '/foto')
    assert response.mimetype == 'image/jpeg'
    assert client.get(path + '/editar').status_code == 200
    assert post(client, path + '/editar', name='Novo nome', description='<script>alert(1)</script>').status_code == 302
    assert collection.find_one()['photo'] == place['photo']
    assert b'&lt;script&gt;' in client.get('/admin/').data
    assert post(client, path + '/editar', name='Novo nome', description='Nova descrição', photo=photo('red')).status_code == 302
    assert collection.find_one()['photo'] != place['photo']
    assert client.get(path + '/remover').status_code == 200
    assert collection.count_documents({}) == 1
    assert post(client, path + '/remover').status_code == 302
    assert collection.count_documents({}) == 0
    assert client.get(path + '/foto').status_code == 404


def test_invalid_inputs(client):
    login(client)
    for data in [dict(name='', description='Text', photo=photo()), dict(name='Place', description='Text'), dict(name='Place', description='Text', photo=(io.BytesIO(b'not an image'), 'photo.png')), dict(name='Place', description='Text', photo=(io.BytesIO(b'x' * (5 * 1024 * 1024 + 1)), 'photo.jpg'))]:
        assert post(client, '/admin/locais/novo', **data).status_code == 400
    assert client.application.extensions['mongo_db'].places.count_documents({}) == 0
    assert client.get('/admin/locais/invalid/editar').status_code == 404


def test_create_admin(client):
    runner = client.application.test_cli_runner()
    result = runner.invoke(args=['create-admin', '--email', 'new@example.com', '--password', 'long-password-123'])
    assert result.exit_code == 0
    user = client.application.extensions['mongo_db'].admins.find_one({'email': 'new@example.com'})
    assert user['password_hash'] != 'long-password-123'
    assert runner.invoke(args=['create-admin', '--email', 'new@example.com', '--password', 'long-password-123']).exit_code != 0


def test_home_login_reaches_admin_dashboard(client):
    home = client.get('/')
    assert b'href="/entrar"' in home.data
    assert b'href="/admin/entrar"' in home.data
    page = client.get('/admin/entrar')
    assert b'name="password"' in page.data
    assert b'name="email"' in page.data
    response = post(client, '/admin/entrar', email='admin@example.com', password='test-password-123')
    assert response.status_code == 302
    assert response.location == '/admin/'
    dashboard = client.get(response.location)
    assert b'Locais cadastrados' in dashboard.data
    assert b'Novo local' in dashboard.data
    assert b'/admin/locais/novo' in dashboard.data
    assert client.get('/admin/entrar', follow_redirects=True).request.path == '/admin/'


def test_user_registration_login_and_role_separation(client):
    page = client.get('/entrar')
    assert page.status_code == 200
    assert b'Entrar como usu' in page.data
    assert client.post('/criar-conta', data={}).status_code == 400
    client.get('/criar-conta')
    assert post(client, '/criar-conta', name='Maria', email='maria@example.com', password='123', confirmation='123').status_code == 400
    credentials = dict(name='Maria', email='maria@example.com', password='user-password-123', confirmation='user-password-123')
    assert post(client, '/criar-conta', **credentials).location == '/entrar'
    assert post(client, '/criar-conta', **credentials).status_code == 400
    assert post(client, '/entrar', email='maria@example.com', password='wrong').status_code == 401
    assert post(client, '/entrar', email='maria@example.com', password='user-password-123').location == '/mapa'
    assert client.get('/admin/').location == '/admin/entrar'
    assert b'Maria' in client.get('/perfil').data
    assert post(client, '/sair').location == '/entrar'
    assert client.get('/entrar').status_code == 200
    client.get('/admin/entrar')
    assert post(client, '/admin/entrar', email='maria@example.com', password='user-password-123').status_code == 401
