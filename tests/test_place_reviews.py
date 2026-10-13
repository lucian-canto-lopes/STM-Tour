import pytest
from test_admin import client, login, photo, post
from test_contributions import member


def make_place(client):
    return str(client.application.extensions['mongo_db'].places.insert_one({
        'name': 'Ilha do Amor', 'description': 'Praia para conhecer', 'category': 'praias', 'photo': b'photo',
        'latitude': -2.44, 'longitude': -54.7,
    }).inserted_id)


def test_review_optional_comment_update_and_average(client):
    key = make_place(client)
    user = member(client)
    other = member(client, 'second@example.com')
    path = f'/locais/{key}/avaliar'
    assert post(user, path, rating='5').status_code == 302
    db = client.application.extensions['mongo_db']
    assert db.place_reviews.find_one()['comment'] == ''
    assert post(other, path, rating='3', comment='<script>alert(1)</script>').status_code == 302
    page = client.get(f'/locais/{key}').text
    assert '4.0' in page and '2 avaliações' in page
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert post(user, path, rating='1', comment='Nova visita').status_code == 302
    assert db.place_reviews.count_documents({}) == 2
    assert '2.0' in client.get(f'/locais/{key}').text
    own = user.get(f'/locais/{key}').text
    assert 'Editar minha avaliação' in own and 'Nova visita</textarea>' in own
    assert 'step="0.5" required value="1.0"' in own


@pytest.mark.parametrize('rating', ['', '0', '6', '-1', 'nan', 'inf', '3.3', '4.25'])
def test_invalid_rating_and_csrf(client, rating):
    key = make_place(client)
    user = member(client)
    path = f'/locais/{key}/avaliar'
    assert user.post(path, data={'rating': '5'}).status_code == 400
    response = post(user, path, rating=rating, comment='Minha visita')
    assert response.status_code == 400
    assert 'Minha visita</textarea>' in response.text
    assert client.application.extensions['mongo_db'].place_reviews.count_documents({}) == 0


def test_reviews_require_login_public_place_and_comment_limit(client):
    key = make_place(client)
    client.get('/entrar')
    assert post(client, f'/locais/{key}/avaliar', rating='5').location == '/entrar'
    user = member(client)
    assert post(user, f'/locais/{key}/avaliar', rating='5', comment='x' * 2001).status_code == 400
    assert post(user, '/locais/invalid/avaliar', rating='5').status_code == 404
    pending = str(client.application.extensions['mongo_db'].contributions.insert_one({'kind': 'new', 'status': 'pending'}).inserted_id)
    assert post(user, f'/locais/{pending}/avaliar', rating='5').status_code == 404
    assert client.application.extensions['mongo_db'].place_reviews.count_documents({}) == 0


def test_dedicated_page_photo_submission_and_favorite(client):
    key = make_place(client)
    user = member(client)
    page = user.get(f'/locais/{key}').text
    assert 'Ilha do Amor · STM Tour' in page and 'Adicionar uma foto' in page
    invalid = post(user, f'/locais/{key}/contribuir', kind='photo', return_to='detail')
    assert invalid.status_code == 400 and 'Selecione uma foto.' in invalid.text and 'Ilha do Amor · STM Tour' in invalid.text
    assert post(user, f'/locais/{key}/contribuir', kind='photo', photo=photo(), return_to='detail').location == f'/locais/{key}#fotos'
    db = client.application.extensions['mongo_db']
    item = db.contributions.find_one({'kind': 'photo'})
    assert item['status'] == 'pending'
    image = f'/contribuicoes/{item["_id"]}/foto'
    assert image not in client.get(f'/locais/{key}').text
    login(client)
    assert post(client, f'/admin/contribuicoes/{item["_id"]}/revisar', decision='approved').status_code == 302
    assert image in client.get(f'/locais/{key}').text
    assert post(user, f'/locais/{key}/favoritar').location == f'/locais/{key}'
    assert 'Remover dos favoritos' in user.get(f'/locais/{key}').text


@pytest.mark.parametrize('rating', ['0.5', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5', '4,5'])
def test_half_star_ratings(client, rating):
    key = make_place(client)
    user = member(client)
    assert post(user, f'/locais/{key}/avaliar', rating=rating).status_code == 302
    saved = client.application.extensions['mongo_db'].place_reviews.find_one()
    assert saved['rating'] == float(rating.replace(',', '.'))
    page = user.get(f'/locais/{key}')
    assert page.status_code == 200 and 'data-star-rating' in page.text
    assert f"--rating-fill: {saved['rating'] * 20}%" in page.text


def test_average_can_differ_from_half_steps(client):
    key = make_place(client)
    for index, rating in enumerate(['3', '3.5', '3.5']):
        user = member(client, f'user{index}@example.com')
        assert post(user, f'/locais/{key}/avaliar', rating=rating).status_code == 302
    assert '<strong>3.3</strong>' in client.get(f'/locais/{key}').text
