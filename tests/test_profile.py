import io
from datetime import datetime, timezone

from test_admin import client, login, photo, post
from test_contributions import member


def test_new_profile_is_empty_and_requires_login(client):
    assert client.get('/perfil').location == '/entrar'
    user = member(client)
    page = user.get('/perfil').text
    assert page.count('<b>0</b>') == 3
    assert 'Você ainda não avaliou nenhum lugar.' in page
    assert 'Ilha do Amor' not in page and 'Cachoeira do Éden' not in page
    assert 'VISITAS' not in page


def test_profile_uses_only_own_activity_and_latest_review(client):
    user = member(client)
    other = member(client, 'other@example.com')
    db = client.application.extensions['mongo_db']
    key = str(db.places.insert_one({'name': 'Praia real', 'description': 'Rio'}).inserted_id)
    assert post(user, f'/locais/{key}/avaliar', rating='5', comment='Minha avaliação').status_code == 302
    assert post(user, f'/locais/{key}/avaliar', rating='4', comment='Atualizada').status_code == 302
    assert post(other, f'/locais/{key}/avaliar', rating='1', comment='Comentário de outra pessoa').status_code == 302
    assert post(user, f'/locais/{key}/contribuir', kind='photo', photo=photo()).status_code == 302
    assert post(user, f'/locais/{key}/contribuir', kind='description', description='Descrição melhor').status_code == 302
    assert post(other, f'/locais/{key}/contribuir', kind='photo', photo=photo()).status_code == 302
    page = user.get('/perfil').text
    assert '<b>2</b><small>CONTRIBUIÇÕES' in page
    assert '<b>1</b><small>AVALIAÇÕES' in page
    assert '<b>1</b><small>FOTOS ENVIADAS' in page
    assert 'Praia real' in page and '★ 4' in page and 'Atualizada' in page
    assert 'Comentário de outra pessoa' not in page
    assert f'/locais/{key}#avaliacoes' in page
    db.places.delete_many({})
    assert 'Ponto indisponível' in user.get('/perfil').text


def test_profile_counts_new_place_photos_and_separates_account_sources(client):
    user = member(client)
    post(user, '/contribuir', name='Praia sugerida', description='Texto', category='praias', latitude='-2', longitude='-54', photo=photo())
    db = client.application.extensions['mongo_db']
    person = db.users.find_one()
    db.contributions.insert_one({'author_id': person['_id'], 'author_source': 'admins', 'kind': 'photo', 'photo': b'other', 'status': 'approved'})
    db.place_reviews.insert_one({'author_id': person['_id'], 'author_source': 'admins', 'place_id': person['_id'], 'rating': 5, 'comment': 'Outra origem', 'updated_at': datetime.now(timezone.utc)})
    page = user.get('/perfil').text
    assert '<b>1</b><small>CONTRIBUIÇÕES' in page
    assert '<b>1</b><small>FOTOS ENVIADAS' in page
    assert '<b>0</b><small>AVALIAÇÕES' in page
    assert 'Outra origem' not in page
    login(client)
    assert client.get('/perfil').status_code == 200


def test_profile_can_update_name_bio_and_photo(client):
    assert client.get('/perfil/editar').location == '/entrar'
    user = member(client)
    database = client.application.extensions['mongo_db']
    person = database.users.find_one({'email': 'member@example.com'})
    database.place_reviews.insert_one({
        'author_id': person['_id'], 'author_source': 'users', 'place_id': person['_id'],
        'rating': 5, 'comment': '', 'author_name': 'Pessoa', 'updated_at': datetime.now(timezone.utc),
    })

    editor = user.get('/perfil/editar')
    assert editor.status_code == 200
    assert 'Editar perfil' in editor.text and 'name="bio"' in editor.text
    response = post(user, '/perfil/editar', name='Ana Tapajós', bio='Viajante, fotógrafa e apaixonada pela Amazônia.', photo=photo('blue'))
    assert response.location == '/perfil'

    person = database.users.find_one({'_id': person['_id']})
    assert person['name'] == 'Ana Tapajós'
    assert person['bio'] == 'Viajante, fotógrafa e apaixonada pela Amazônia.'
    assert person['profile_photo'].startswith(b'\xff\xd8')
    assert database.place_reviews.find_one()['author_name'] == 'Ana Tapajós'
    page = user.get('/perfil').text
    assert 'Ana Tapajós' in page and person['bio'] in page
    assert 'aria-label="Editar perfil"' in page and '/perfil/foto' in page
    image = user.get('/perfil/foto')
    assert image.status_code == 200 and image.mimetype == 'image/jpeg'


def test_profile_edit_validates_fields_and_image(client):
    user = member(client)
    assert post(user, '/perfil/editar', name='', bio='Texto').status_code == 400
    assert post(user, '/perfil/editar', name='Pessoa', bio='x' * 151).status_code == 400
    response = post(user, '/perfil/editar', name='Pessoa', bio='Texto', photo=(io.BytesIO(b'not-image'), 'photo.png'))
    assert response.status_code == 400
    oversized = post(user, '/perfil/editar', name='Pessoa', bio='Texto', photo=(io.BytesIO(b'x' * (6 * 1024 * 1024 + 1)), 'photo.jpg'))
    assert oversized.status_code == 413 and 'A foto deve ter no máximo 5 MB.' in oversized.text
    person = client.application.extensions['mongo_db'].users.find_one()
    assert 'bio' not in person and 'profile_photo' not in person


def test_legacy_admin_can_edit_profile(client):
    login(client)
    assert post(client, '/perfil/editar', name='Administrador', bio='Cuido dos pontos publicados.').location == '/perfil'
    administrator = client.application.extensions['mongo_db'].admins.find_one()
    assert administrator['name'] == 'Administrador'
    assert administrator['bio'] == 'Cuido dos pontos publicados.'
