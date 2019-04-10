import os
import pytest
import subprocess

from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.composition import Composition
from c2cwsgiutils.acceptance.connection import Connection

from acceptance import BASE_URL, PROJECT_NAME


@pytest.yield_fixture(scope="package")
def composition(request, test_repos):
    """
    Fixture that start/stop the Docker composition used for all the tests.
    """
    for slave in ('api', 'slave'):
        path = os.path.join('/tmp/slaves', slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    result = Composition(request, PROJECT_NAME, '/acceptance_tests/acceptance/inline/docker-compose.yaml',
                         coverage_paths=[PROJECT_NAME + "_api_1:/tmp/coverage"])
    utils.wait_url(BASE_URL + 'c2c/health_check?max_level=2')

    yield result

    subprocess.check_call("rm -rf /tmp/slaves/*", shell=True)


@pytest.fixture
def app_connection(composition):
    """
    Fixture that returns a connection to a running batch container.
    """
    return Connection(base_url=BASE_URL, origin='http://example.com/')
