import logging
import os
import pytest
import requests
import subprocess

from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.composition import Composition
from c2cwsgiutils.acceptance.connection import Connection

BASE_URL = 'http://' + utils.DOCKER_GATEWAY + ':8080/scm/'
PROJECT_NAME = 'scm'
LOG = logging.getLogger(__name__)


def wait_slaves():
    def what() -> bool:
        r = requests.get(BASE_URL + '1/status/changeme')
        if r.status_code == 200:
            json = r.json()
            if len(json['slaves']) != 3:
                raise Exception("Not seeing 3 slaves")
            for name, status in json['slaves'].items():
                if name == 'slave-others':
                    if set(status['sources'].keys()) != {'master'}:
                        raise Exception(f"Not seeing the 1 source on {name}")
                else:
                    if set(status['sources'].keys()) != {'master', 'test_git'}:
                        raise Exception(f"Not seeing the 2 sources on {name}")
            return True
        else:
            raise Exception(f"Not having a 200 status: {r.status_code}")

    utils.retry_timeout(what)


@pytest.yield_fixture(scope="session")
def composition(request, test_repos):
    """
    Fixture that start/stop the Docker composition used for all the tests.
    """
    for slave in ('api', 'slave'):
        path = os.path.join('/tmp/slaves', slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    result = Composition(request, PROJECT_NAME, '/acceptance_tests/docker-compose.yaml',
                         coverage_paths=[
                             PROJECT_NAME + "_api_1:/tmp/coverage",
                             PROJECT_NAME + "_slave_1:/tmp/coverage"
                         ])
    utils.wait_url(BASE_URL + 'c2c/health_check?max_level=2')
    wait_slaves()

    yield result

    subprocess.check_call("rm -rf /tmp/slaves/*", shell=True)


@pytest.fixture
def app_connection(composition):
    """
    Fixture that returns a connection to a running batch container.
    """
    return Connection(base_url=BASE_URL, origin='http://example.com/')


@pytest.yield_fixture(scope="session")
def test_repos():
    subprocess.check_call(['git', 'config', '--global', 'user.email', "you@example.com"])
    subprocess.check_call(['git', 'config', '--global', 'user.name', "Your Name"])
    location = '/tmp/test_repos'
    subprocess.check_call(['/acceptance_tests/create_test_repos'], cwd='/tmp')
    subprocess.check_call(['chown', '-R', 'www-data:root', location])
    yield location
    subprocess.check_call(['bash', '-c', f'rm -r {location}/*'])
