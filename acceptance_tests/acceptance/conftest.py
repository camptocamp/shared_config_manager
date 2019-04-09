import pytest
import subprocess


@pytest.yield_fixture(scope="session")
def test_repos():
    subprocess.check_call(['git', 'config', '--global', 'user.email', "you@example.com"])
    subprocess.check_call(['git', 'config', '--global', 'user.name', "Your Name"])
    location = '/tmp/test_repos'
    subprocess.check_call(['/acceptance_tests/create_test_repos'], cwd='/tmp')
    subprocess.check_call(['chown', '-R', 'www-data:root', location])
    yield location
    subprocess.check_call(['bash', '-c', f'rm -r {location}/*'])
