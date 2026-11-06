import pytest

from test_admin import client, login, post
from test_contributions import member
from test_place_reviews import make_place


def setup_report(client):
    place = make_place(client)
    author = member(client)
    reporter = member(client, 'reporter@example.com')
    post(author, f'/locais/{place}/avaliar', rating='4', comment='Comentário denunciado')
    database = client.application.extensions['mongo_db']
    review = database.place_reviews.find_one()
    path = f'/locais/{place}/comentarios/{review["_id"]}/denunciar'
    return place, author, reporter, database, path


@pytest.mark.parametrize('decision', ['approved', 'rejected'])
def test_report_moderation(client, decision):
    place, author, reporter, database, path = setup_report(client)
    assert 'Denunciar comentário' in reporter.get(f'/locais/{place}').text
    assert post(reporter, path, reason='<script>Motivo</script>', status='approved').status_code == 302
    report = database.comment_reports.find_one()
    assert report['status'] == 'pending'
    assert 'Comentário denunciado' in client.get(f'/locais/{place}').text
    assert post(reporter, path, reason='Repetida').status_code == 302
    assert database.comment_reports.count_documents({}) == 1
    review_path = f'/admin/denuncias/{report["_id"]}/revisar'
    assert reporter.get('/admin/denuncias').status_code == 403
    assert post(reporter, review_path, decision=decision).status_code == 403
    login(client)
    assert '&lt;script&gt;Motivo&lt;/script&gt;' in client.get('/admin/denuncias').text
    assert client.post(review_path, data={'decision': decision}).status_code == 400
    assert post(client, review_path, decision='invalid').status_code == 400
    assert post(client, review_path, decision=decision).status_code == 302
    assert post(client, review_path, decision=decision).status_code == 409
    page = author.get(f'/locais/{place}').text
    assert ('Comentário denunciado' in page) == (decision == 'rejected')
    assert '<strong>4.0</strong>' in page
    saved = database.comment_reports.find_one()
    assert saved['status'] == decision and saved['reviewer']['author_source'] == 'admins'


def test_report_validation_and_missing_targets(client):
    place, author, reporter, database, path = setup_report(client)
    client.get('/entrar')
    assert post(client, path, reason='Motivo').location == '/entrar'
    assert reporter.post(path, data={'reason': 'Motivo'}).status_code == 400
    for reason in ('', '  ', 'x' * 1001):
        assert post(reporter, path, reason=reason).status_code == 400
    assert post(reporter, path.replace(place, make_place(client)), reason='Motivo').status_code == 404
    assert post(reporter, f'/locais/{place}/comentarios/invalid/denunciar', reason='Motivo').status_code == 404
    post(author, f'/locais/{place}/avaliar', rating='4', comment='')
    assert post(reporter, path, reason='Motivo').status_code == 404
    assert database.comment_reports.count_documents({}) == 0


def test_decision_preserves_later_edit(client):
    place, author, reporter, database, path = setup_report(client)
    post(reporter, path, reason='Motivo')
    report = database.comment_reports.find_one()
    post(author, f'/locais/{place}/avaliar', rating='4', comment='Comentário corrigido')
    login(client)
    assert post(client, f'/admin/denuncias/{report["_id"]}/revisar', decision='approved').status_code == 302
    assert 'Comentário corrigido' in client.get(f'/locais/{place}').text
    post(reporter, path, reason='Novo motivo')
    assert database.comment_reports.count_documents({}) == 2
