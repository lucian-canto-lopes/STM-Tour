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
