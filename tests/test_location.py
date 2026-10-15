import base64
import re

import pytest
from app.location import coordinates
from test_admin import client, login, photo, post
from test_contributions import member


@pytest.mark.parametrize('latitude,longitude', [('', ''), ('91', '0'), ('0', '-181'), ('nan', '0'), ('0', 'inf'), ('abc', '2'), ('2', '')])
def test_invalid_coordinates(latitude, longitude):
    with pytest.raises(ValueError):
        coordinates({'latitude': latitude, 'longitude': longitude})


def test_coordinate_formats():
    assert coordinates({'latitude': '-2,4431', 'longitude': '-54.7083'}) == {'latitude': -2.4431, 'longitude': -54.7083}
    assert coordinates({'latitude': '0', 'longitude': '0'}) == {'latitude': 0, 'longitude': 0}
    assert coordinates({}, required=False) == {}


def test_map_publishes_pin_only_after_approval(client):
    user = member(client)
    form = user.get('/contribuir').text
    assert 'Escolher no mapa' in form and 'name="latitude"' in form
    assert post(user, '/contribuir', name='Ponto com pin', description='Vista do rio', latitude='-2,44', longitude='-54.70', photo=photo()).status_code == 302
    item = client.application.extensions['mongo_db'].contributions.find_one()
    assert item['latitude'] == -2.44
    assert 'L.marker(' not in client.get('/mapa/conteudo').text
    login(client)
    assert '-2.44, -54.7' in client.get('/admin/contribuicoes').text
    assert post(client, f"/admin/contribuicoes/{item['_id']}/revisar", decision='approved').status_code == 302
    rendered = client.get('/mapa/conteudo').text
    assert 'L.marker(' in rendered and '[-2.44, -54.7]' in rendered
    cards = re.findall(r'data:text/html;charset=utf-8;base64,([^"\s]+)', rendered)
    assert cards
    card = base64.b64decode(cards[0]).decode()
    assert 'Ponto com pin' in card and 'Vista do rio' in card
    assert f'http://localhost/locais/{item["_id"]}' in card and 'target="_top"' in card


def test_map_skips_missing_locations_and_escapes_popup(client):
    db = client.application.extensions['mongo_db']
    db.places.insert_one({'name': 'Sem localização', 'description': 'Texto'})
    db.contributions.insert_one({'name': 'Rejeitado', 'kind': 'new', 'status': 'rejected', 'latitude': 1, 'longitude': 2})
    key = db.places.insert_one({'name': '<script>alert(1)</script>', 'description': '${alert(1)}`</script>', 'latitude': 0, 'longitude': 0}).inserted_id
    page = client.get('/mapa/conteudo')
    assert page.status_code == 200
    assert page.text.count('L.marker(') == 1
    card = base64.b64decode(re.findall(r'data:text/html;charset=utf-8;base64,([^"\s]+)', page.text)[0]).decode()
    assert '<script>alert(1)</script>' not in card
    assert '&lt;script&gt;' in card
    assert str(key) in card


def test_invalid_submission_preserves_values_and_admin_location(client):
    user = member(client)
    response = post(user, '/contribuir', name='Praia', description='Texto', latitude='100', longitude='-54', photo=photo())
    assert response.status_code == 400 and 'value="100"' in response.text
    assert client.application.extensions['mongo_db'].contributions.count_documents({}) == 0
    login(client)
    assert post(client, '/admin/locais/novo', name='Praia', description='Texto', latitude='-2.5', longitude='-54.8', photo=photo()).status_code == 302
    place = client.application.extensions['mongo_db'].places.find_one()
    assert place['latitude'] == -2.5
    edit = client.get(f'/admin/locais/{place["_id"]}/editar').text
    assert 'value="-2.5"' in edit
    assert client.get('/mapa/selecionar').status_code == 200
    assert re.search(r'"?scrollWheelZoom"?\s*:\s*true', client.get('/mapa/conteudo').text)


def test_map_zoom_out_limit_covers_region_and_adapts_to_screen(client):
    from app.routes import SANTAREM_MAP_BOUNDS

    south_west, north_east = SANTAREM_MAP_BOUNDS
    # Sede, Alter do Chão e uma comunidade na região do Arapiuns.
    for latitude, longitude in [(-2.4431, -54.7083), (-2.506, -54.951), (-2.75, -55.6)]:
        assert south_west[0] <= latitude <= north_east[0]
        assert south_west[1] <= longitude <= north_east[1]
    html = client.get('/mapa/conteudo').text
    assert 'L.latLngBounds([[-4.1, -56.1], [-1.9, -53.9]])' in html
    assert 'setMinZoom(regionalMap.getBoundsZoom(regionalBounds, false))' in html
    assert "regionalMap.on('resize', updateRegionalZoomLimit)" in html
    assert 'regionalMap.whenReady(updateRegionalZoomLimit)' in html
    assert 'updateRegionalZoomLimit' not in client.get('/mapa/selecionar').text
