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


def test_webhook(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/master"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'push'})

    assert answer == {
        'status': 200,
        'nb_completed': 2
    }


def test_webhook_other_branch(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/other"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'push'})

    assert answer == {
        'status': 200,
        'nb_completed': 0
    }


def test_webhook_not_push(app_connection):
    answer = app_connection.post_json('1/refresh/test_git/changeme', json={
        "ref": "refs/heads/master"
        # the rest is ignored
    }, headers={'X-GitHub-Event': 'pull_request'})

    assert answer == {
        'status': 200,
        'nb_completed': 0
    }
