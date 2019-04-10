def test_ok(app_connection):
    answer = app_connection.get_json('1/refresh/test_git/changeme')
    assert answer == {
        'status': 200
    }


def test_bad_key(app_connection):
    app_connection.get_json('1/refresh/test_git/bad', expected_status=403)


def test_bad_id(app_connection):
    app_connection.get_json('1/refresh/unknown/changeme', expected_status=404)


def test_webhook(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/master"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'push'})

    assert answer == {
        'status': 200
    }


def test_webhook_other_branch(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/other"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'push'})

    assert answer == {
        'status': 200,
        'ignored': True,
        'reason': 'Not master branch'
    }


def test_webhook_not_push(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/master"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'pull_request'})

    assert answer == {
        'status': 200,
        'ignored': True,
        'reason': 'Not a push'
    }


def test_all(app_connection):
    answer = app_connection.get_json('1/refresh/changeme')
    assert answer == {
        'status': 200,
        'nb_refresh': 1
    }


def test_all_webhook(app_connection):
    answer = app_connection.post_json('1/refresh/changeme', json={
        "ref": "refs/heads/master"
    }, headers={'X-GitHub-Event': 'push'})
    assert answer == {
        'status': 200,
        'nb_refresh': 1
    }


def test_all_bad_key(app_connection):
    app_connection.get_json('1/refresh/bad', expected_status=403)
