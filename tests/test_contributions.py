from test_admin import client, login, photo, post
from werkzeug.security import generate_password_hash


def member(client, email='member@example.com'):
    client.application.extensions['mongo_db'].users.insert_one({
        'name': 'Pessoa', 'email': email, 'password_hash': generate_password_hash('password'), 'role': 'user'})
    browser = client.application.test_client()
    browser.get('/entrar')
    post(browser, '/entrar', email=email, password='password')
    browser.get('/contribuir')
    return browser


def test_new_place_private_until_approved(client):
    user = member(client)
    other = member(client, 'other@example.com')
    assert post(user, '/contribuir', name='Praia nova', latitude='-2.44', longitude='-54.70', description='Descrição inédita', photo=photo(), status='approved').location == '/minhas-contribuicoes'
    database = client.application.extensions['mongo_db']
    item = database.contributions.find_one()
    assert item['status'] == 'pending'
    key = str(item['_id'])
    image = f'/contribuicoes/{key}/foto'
    assert b'Praia nova' not in client.get('/locais').data
    assert client.get(f'/locais/{key}').status_code == 404
    assert client.get(f'/locais/{key}/foto').status_code == 404
    assert client.get(image).status_code == 404
    assert other.get(image).status_code == 404
    assert user.get(image).status_code == 200
    assert b'Praia nova' in user.get('/minhas-contribuicoes').data
    assert b'Praia nova' not in other.get('/minhas-contribuicoes').data
    assert user.get('/admin/contribuicoes').status_code == 403
    review = f'/admin/contribuicoes/{key}/revisar'
    assert post(user, review, decision='approved').status_code == 403
    login(client)
    assert client.get(image).status_code == 200
    assert b'Praia nova' in client.get('/admin/contribuicoes').data
    assert client.post(review, data={'decision': 'approved'}).status_code == 400
    assert post(client, review, decision='approved').status_code == 302
    assert post(client, review, decision='rejected').status_code == 409
    assert b'Praia nova' in other.get('/locais').data
    assert 'Descrição inédita' in other.get(f'/locais/{key}').text
    assert other.get(f'/locais/{key}/foto').status_code == 200
    assert other.get(image).status_code == 200
    assert database.contributions.find_one() ['reviewer']['author_source'] == 'admins'


def test_existing_place_description_and_photo_moderation(client):
    database = client.application.extensions['mongo_db']
    key = str(database.places.insert_one({'name': 'Praia', 'description': 'Original', 'photo': b'original'}).inserted_id)
    user = member(client)
    path = f'/locais/{key}/contribuir'
    assert post(user, path, kind='description', description='Nova descrição').status_code == 302
    desc = database.contributions.find_one({'kind': 'description'})
    assert post(user, path, kind='photo', photo=photo()).status_code == 302
    picture = database.contributions.find_one({'kind': 'photo'})
    assert 'Original' in user.get(f'/locais/{key}').text
    assert str(picture['_id']) not in user.get(f'/locais/{key}').text
    login(client)
    assert 'Original' in client.get('/admin/contribuicoes').text
    assert post(client, f"/admin/contribuicoes/{desc['_id']}/revisar", decision='approved').status_code == 302
    assert 'Nova descrição' in user.get(f'/locais/{key}').text
    assert post(client, f"/admin/contribuicoes/{picture['_id']}/revisar", decision='rejected').status_code == 302
    assert str(picture['_id']) not in user.get(f'/locais/{key}').text
    assert client.application.test_client().get(f"/contribuicoes/{picture['_id']}/foto").status_code == 404
    assert 'Rejeitada' in user.get('/minhas-contribuicoes').text
    assert post(user, path, kind='photo', photo=photo()).status_code == 302
    pending = database.contributions.find_one({'status': 'pending'})
    assert post(client, f"/admin/contribuicoes/{pending['_id']}/revisar", decision='approved').status_code == 302
    assert str(pending['_id']) in user.get(f'/locais/{key}').text
    assert database.places.find_one()['photo'] == b'original'


def test_invalid_submissions_and_missing_targets(client):
    assert client.get('/contribuir').location == '/entrar'
    user = member(client)
    assert user.post('/contribuir').status_code == 400
    assert post(user, '/contribuir', name='X', description='Y').status_code == 400
    assert post(user, '/contribuir', name='', description='Y', photo=photo()).status_code == 400
    assert user.get('/locais/invalid/contribuir').status_code == 404
    database = client.application.extensions['mongo_db']
    key = database.places.insert_one({'name': 'X', 'description': 'Y'}).inserted_id
    assert post(user, f'/locais/{key}/contribuir', kind='admin', description='X').status_code == 400
    assert post(user, f'/locais/{key}/contribuir', kind='description', description='').status_code == 400
    assert database.contributions.count_documents({}) == 0
    post(user, f'/locais/{key}/contribuir', kind='description', description='Nova')
    item = database.contributions.find_one()
    database.places.delete_one({'_id': key})
    login(client)
    assert client.get('/admin/contribuicoes').status_code == 200
    assert post(client, f"/admin/contribuicoes/{item['_id']}/revisar", decision='approved').status_code == 404
    assert post(client, f"/admin/contribuicoes/{item['_id']}/revisar", decision='rejected').status_code == 302
