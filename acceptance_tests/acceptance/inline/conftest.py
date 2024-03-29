import os

import pytest
from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.connection import Connection


@pytest.fixture(scope="package")
def composition(request):
    """
    Fixture that will wait that the composition is started, used for all the tests.
    """
    for slave in ("api",):
        path = os.path.join("/config", slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    utils.wait_url("http://api_inline:8080/scm/c2c/health_check?max_level=2")

    yield None


@pytest.fixture
def app_connection(composition):
    """
    Fixture that returns a connection to a running batch container.
    """
    return Connection(base_url="http://api_inline:8080/scm/", origin="http://example.com/")
