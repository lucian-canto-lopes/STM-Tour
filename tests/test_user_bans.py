from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from test_admin import client, login, post
from test_contributions import member
from test_place_reviews import make_place


@pytest.mark.parametrize('kind', ['temporary', 'permanent'])
def test_ban_blocks_login_active_session_and_unban(client, kind):
    user = member(client)
    database = client.application.extensions['mongo_db']
    account = database.users.find_one({'email': 'member@example.com'})
    place = make_place(client)
    login(client)
    path = f'/admin/usuarios/{account["_id"]}'
    assert post(client, path + '/banir', kind=kind, days='7', reason='Abuso nos comentários').status_code == 302
    banned = database.users.find_one({'_id': account['_id']})
    assert banned['ban']['kind'] == kind and banned['auth_version'] == 1
    assert ('until' in banned['ban']) == (kind == 'temporary')
    page = client.get('/admin/usuarios').text
    assert 'Abuso nos comentários' in page and 'Remover banimento' in page
    assert path + '/promover' not in page
    assert post(client, path + '/promover').status_code == 409
    assert post(user, f'/locais/{place}/avaliar', rating='5').location == '/entrar'
    assert database.place_reviews.count_documents({}) == 0
    user.get('/entrar')
    assert post(user, '/entrar', email=account['email'], password='password').status_code == 403
    assert post(client, path + '/desbanir').status_code == 302
    user.get('/entrar')
    assert post(user, '/entrar', email=account['email'], password='password').location == '/mapa'
    assert user.get('/perfil').status_code == 200


def test_temporary_ban_expires_but_old_sessions_stay_invalid(client):
    user = member(client)
    database = client.application.extensions['mongo_db']
    account = database.users.find_one()
    login(client)
    post(client, f'/admin/usuarios/{account["_id"]}/banir', kind='temporary', days='1', reason='Motivo')
    database.users.update_one({'_id': account['_id']}, {'$set': {
        'ban.until': datetime.now(timezone.utc) - timedelta(seconds=1)}})
    assert user.get('/perfil').location == '/entrar'
    user.get('/entrar')
    assert post(user, '/entrar', email=account['email'], password='password').location == '/mapa'
    assert 'Banido temporariamente' not in client.get('/admin/usuarios').text


def test_ban_permissions_validation_and_admin_protection(client):
    user = member(client)
    database = client.application.extensions['mongo_db']
    account = database.users.find_one()
    path = f'/admin/usuarios/{account["_id"]}'
    assert post(user, path + '/banir', kind='permanent', reason='Motivo').status_code == 403
    assert post(user, path + '/desbanir').status_code == 403
    login(client)
    assert client.post(path + '/banir').status_code == 400
    assert client.post(path + '/desbanir').status_code == 400
    for data in ({'kind': 'invalid', 'reason': 'Motivo'}, {'kind': 'permanent', 'reason': ''},
                 {'kind': 'permanent', 'reason': 'x' * 1001},
                 {'kind': 'temporary', 'reason': 'Motivo', 'days': '-1'},
                 {'kind': 'temporary', 'reason': 'Motivo', 'days': '99999'}):
        assert post(client, path + '/banir', **data).status_code == 400
    assert 'ban' not in database.users.find_one({'_id': account['_id']})
    for key in ('invalid', str(ObjectId())):
        assert post(client, f'/admin/usuarios/{key}/banir', kind='permanent', reason='Motivo').status_code == 404
        assert post(client, f'/admin/usuarios/{key}/desbanir').status_code == 404
    post(client, path + '/promover')
    assert post(client, path + '/banir', kind='permanent', reason='Motivo').status_code == 403
    assert 'Conta administrativa protegida' in client.get('/admin/usuarios').text
