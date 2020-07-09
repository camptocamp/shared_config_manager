import logging
import os
import subprocess

import pytest
import requests
from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.connection import Connection

LOG = logging.getLogger(__name__)


def wait_slaves():
    def what() -> bool:
        r = requests.get("http://api:8080/scm/1/status/changeme")
        if r.status_code == 200:
            json = r.json()
            if len(json["slaves"]) != 3:
                raise Exception(f"Not seeing 3 slaves but {len(json['slaves'])}.",)
            for name, status in json["slaves"].items():
                if name == "slave-others":
                    if set(status["sources"].keys()) != {"master"}:
                        raise Exception(f"Not seeing the 1 source on {name}")
                else:
                    if set(status["sources"].keys()) != {"master", "test_git"}:
                        raise Exception(f"Not seeing the 2 sources on {name}: {status['sources'].keys()}")
            return True
        else:
            LOG.warning("%i, %s: %s", r.status_code, r.status, r.text)
            raise Exception(f"Not having a 200 status: {r.status_code}")

    utils.retry_timeout(what)


@pytest.yield_fixture(scope="package")
def composition(request):
    """
    Fixture that start/stop the Docker composition used for all the tests.
    """
    for slave in ("api", "slave", "slave-others"):
        path = os.path.join("/config", slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    utils.wait_url("http://api:8080/scm/c2c/health_check?max_level=2")
    wait_slaves()

    yield None

    subprocess.check_call("rm -rf /config/*", shell=True)


@pytest.fixture
def app_connection(composition):
    """
    Fixture that returns a connection to a running batch container.
    """
    return Connection(base_url="http://api:8080/scm/", origin="http://example.com/")
