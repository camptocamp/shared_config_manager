import os
import pytest
import subprocess
import tempfile

from shared_config_manager import sources

TEMP_DIR = tempfile.gettempdir()


@pytest.yield_fixture()
def repo():
    repo_path = os.path.join(TEMP_DIR, 'repo')
    subprocess.check_call(['git', 'config', '--global', 'user.email', 'you@example.com'],
                          stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'config', '--global', 'user.name', 'Your Name'],
                          stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'init', repo_path], stderr=subprocess.STDOUT)
    file_path = os.path.join(repo_path, 'test')
    with open(file_path, 'w') as file:
        file.write('Hello world')
    subprocess.check_call(['git', 'add', file_path], cwd=repo_path, stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'commit', '-a', '-m', 'Initial commit'], cwd=repo_path,
                          stderr=subprocess.STDOUT)

    yield repo_path

    subprocess.check_call(['rm', '-rf', repo_path], stderr=subprocess.STDOUT)


def test_git(repo):
    git = sources._create_source('test_git', {
        'type': 'git',
        'key': 'changeme',
        'repo': repo
    })

    git.refresh()
    assert os.path.isfile('/config/test_git/test')
    with open('/config/test_git/test') as file:
        assert file.read() == 'Hello world'

    repo_file_path = os.path.join(repo, 'test')
    with open(repo_file_path, 'w') as file:
        file.write('Good bye')
    subprocess.check_call(['git', 'add', repo_file_path], cwd=repo, stderr=subprocess.STDOUT)
    subprocess.check_call(['git', 'commit', '-a', '-m', 'Initial commit'],
                          cwd=repo, stderr=subprocess.STDOUT)

    git.refresh()
    assert os.path.isfile('/config/test_git/test')
    with open('/config/test_git/test') as file:
        assert file.read() == 'Good bye'
