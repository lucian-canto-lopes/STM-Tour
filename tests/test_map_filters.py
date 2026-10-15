from test_admin import client, login, photo, post
from test_contributions import member


def test_search_and_category_filter_pins(client):
    db = client.application.extensions['mongo_db']
    db.places.insert_many([
        {'name': 'Praia do Amor', 'description': 'Águas claras', 'category': 'praias', 'latitude': -2, 'longitude': -54},
        {'name': 'Café do Amor', 'description': 'Comida regional', 'category': 'gastronomia', 'latitude': -3, 'longitude': -55},
        {'name': 'Antigo', 'description': 'Texto', 'latitude': -4, 'longitude': -56},
    ])
    assert client.get('/mapa/conteudo?q=amor').text.count('L.marker(') == 2
    assert client.get('/mapa/conteudo?q=aguas&category=praias').text.count('L.marker(') == 1
    assert client.get('/mapa/conteudo?q=cafe&category=praias').text.count('L.marker(') == 0
    assert client.get('/mapa/conteudo?category=outros').text.count('L.marker(') == 1
    assert 'Nenhum lugar encontrado' in client.get('/mapa?q=inexistente').text
    assert 'aria-pressed="true">Praias' in client.get('/mapa?category=praias').text
    page = client.get('/mapa').text
    assert 'class="place-card"' not in page
    assert 'class="interactive-map"' in page


def test_category_saved_validated_and_moderated(client):
    user = member(client)
    assert post(user, '/contribuir', name='Restaurante', description='Comida', category='gastronomia', latitude='-2', longitude='-54', photo=photo()).status_code == 302
    db = client.application.extensions['mongo_db']
    item = db.contributions.find_one()
    assert item['category'] == 'gastronomia'
    assert client.get('/mapa/conteudo?category=gastronomia').text.count('L.marker(') == 0
    login(client)
    post(client, f"/admin/contribuicoes/{item['_id']}/revisar", decision='approved')
    assert client.get('/mapa/conteudo?category=gastronomia').text.count('L.marker(') == 1
    assert post(client, '/admin/locais/novo', name='Museu', description='História', category='invalida', latitude='-2', longitude='-54', photo=photo()).status_code == 400
    assert post(client, '/admin/locais/novo', name='Museu', description='História', category='cultura', latitude='-2', longitude='-54', photo=photo()).status_code == 302
    place = db.places.find_one()
    assert place['category'] == 'cultura'
    assert 'selected>Cultura' in client.get(f"/admin/locais/{place['_id']}/editar").text
    assert post(client, f"/admin/locais/{place['_id']}/editar", name='Museu', description='História', category='natureza', latitude='-2', longitude='-54').status_code == 302
    assert db.places.find_one()['category'] == 'natureza'


def test_custom_category_reusable_and_filterable(client):
    login(client)
    data = dict(name='Hotel', description='Estadia', category='outros', new_category='Hospedagem', latitude='-2', longitude='-54')
    assert post(client, '/admin/locais/novo', **data).status_code == 400
    db = client.application.extensions['mongo_db']
    assert db.place_categories.count_documents({}) == 0
    assert post(client, '/admin/locais/novo', **data, photo=photo()).status_code == 302
    place = db.places.find_one()
    category = place['category']
    assert category == 'custom-hospedagem'
    assert db.place_categories.find_one() ['name'] == 'Hospedagem'
    assert f'value="{category}"' in client.get('/admin/locais/novo').text
    user = member(client)
    assert f'value="{category}"' in user.get('/contribuir').text
    assert post(user, '/contribuir', name='Pousada', description='Descanso', category=category, latitude='-3', longitude='-55', photo=photo()).status_code == 302
    item = db.contributions.find_one()
    assert item['category'] == category
    assert post(client, f"/admin/contribuicoes/{item['_id']}/revisar", decision='approved').status_code == 302
    assert client.get(f'/mapa/conteudo?category={category}').text.count('L.marker(') == 2
    assert 'Hospedagem' in client.get(f'/mapa?category={category}').text
    assert client.get('/mapa/conteudo?q=hospedagem').text.count('L.marker(') == 2
    assert post(client, '/admin/locais/novo', **{**data, 'new_category': ' HOSPEDAGEM '}, photo=photo()).status_code == 302
    assert db.place_categories.count_documents({}) == 1
    assert post(client, '/admin/locais/novo', **{**data, 'new_category': 'Praias'}, photo=photo()).status_code == 302
    assert db.places.find_one({'category': 'praias'})
    assert post(client, '/admin/locais/novo', **{**data, 'new_category': 'x' * 61}, photo=photo()).status_code == 400
    assert post(client, '/admin/locais/novo', **{**data, 'new_category': '!!!'}, photo=photo()).status_code == 400
