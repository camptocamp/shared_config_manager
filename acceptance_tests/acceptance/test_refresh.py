def test_ok(app_connection):
    answer = app_connection.get_json('1/refresh/test_git/changeme')
    assert answer == {
        'status': 200,
        'nb_completed': 2
    }
