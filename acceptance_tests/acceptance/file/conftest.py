import os

import pytest
from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.connection import Connection


@pytest.fixture(scope="package")
def composition(request):
    """
    Fixture that will wait that the composition is started, used for all the tests.
    """
    del request
    for slave in ("api",):
        path = os.path.join("/config", slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    utils.wait_url("http://api_file:8080/scm/c2c/health_check?max_level=2")

    yield None


@pytest.fixture
def app_connection(composition):  # pylint: disable=redefined-outer-name
    """
    Fixture that returns a connection to a running batch container.
    """
    del composition
    return Connection(base_url="http://api_file:8080/scm/", origin="http://example.com/")
