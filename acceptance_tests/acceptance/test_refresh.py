def test_ok(app_connection):
    answer = app_connection.get_json('1/refresh/test_git/changeme')
    assert answer == {
        'status': 200,
        'nb_completed': 2
    }


def test_bad_key(app_connection):
    app_connection.get_json('1/refresh/test_git/bad', expected_status=403)


def test_bad_id(app_connection):
    app_connection.get_json('1/refresh/unknown/changeme', expected_status=404)
