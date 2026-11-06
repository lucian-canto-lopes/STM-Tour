from test_admin import client, post
from test_comment_reports import setup_report
from test_place_reviews import make_place


def test_like_unlike_and_independent_users(client):
    place, author, user, database, report_path = setup_report(client)
    path = report_path.replace('/denunciar', '/curtir')
    assert post(user, path).location == f'/locais/{place}#avaliacoes'
    assert database.comment_likes.count_documents({}) == 1
    page = user.get(f'/locais/{place}').text
    assert 'class="comment-like" aria-pressed="true"' in page
    assert '<span>1</span><span class="sr-only">curtidas</span>' in page
    assert 'class="comment-menu"' in page
    assert '</svg>Denunciar</summary>' in page
    assert 'class="comment-like" aria-pressed="false"' in author.get(f'/locais/{place}').text
    post(author, path)
    assert database.comment_likes.count_documents({}) == 2
    post(user, path)
    assert database.comment_likes.count_documents({}) == 1
    assert 'class="comment-like" aria-pressed="false"' in user.get(f'/locais/{place}').text
    assert '<span>1</span><span class="sr-only">curtidas</span>' in client.get(f'/locais/{place}').text
    assert database.place_reviews.find_one()['rating'] == 4


def test_like_requires_login_csrf_and_visible_comment(client):
    place, author, user, database, report_path = setup_report(client)
    path = report_path.replace('/denunciar', '/curtir')
    client.get('/entrar')
    assert post(client, path).location == '/entrar'
    assert user.post(path).status_code == 400
    assert post(user, path.replace(place, make_place(client))).status_code == 404
    assert post(user, f'/locais/{place}/comentarios/invalid/curtir').status_code == 404
    review = database.place_reviews.find_one()
    database.place_reviews.update_one({'_id': review['_id']}, {'$set': {'comment_hidden': True}})
    assert post(user, path).status_code == 404
    assert 'class="comment-menu"' not in user.get(f'/locais/{place}').text
    database.place_reviews.update_one({'_id': review['_id']}, {'$set': {'comment_hidden': False, 'comment': ''}})
    assert post(user, path).status_code == 404
    assert database.comment_likes.count_documents({}) == 0
