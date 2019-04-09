import os

from acceptance import get_hash, wait_sync


def test_ok(app_connection, test_repos):
    test_git_hash = get_hash(os.path.join(test_repos, 'test_git'))
    wait_sync(app_connection, 'test_git', test_git_hash)

    with open(os.path.join('/tmp', 'slaves', 'api', 'test_git', 'test')) as config:
        assert config.read() == 'Hello world\n'
