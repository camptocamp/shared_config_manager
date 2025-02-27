import logging
import os

import pytest
import requests
from c2cwsgiutils.acceptance import utils
from c2cwsgiutils.acceptance.connection import Connection

LOG = logging.getLogger(__name__)


def wait_slaves() -> None:
    """Wait for the slaves to be up."""

    def what() -> bool:
        r = requests.get("http://api:8080/scm/1/status", headers={"X-Scm-Secret": "changeme"})
        if r.status_code == 200:
            json = r.json()
            if len(json["slaves"]) != 4:
                raise Exception(  # pylint: disable=broad-exception-raised
                    f"Not seeing 4 slaves but {len(json['slaves'])}.",
                )
            for name, status in json["slaves"].items():
                if name == "slave-others":
                    if set(status["sources"].keys()) != {"master"}:
                        raise Exception(  # pylint: disable=broad-exception-raised
                            f"Not seeing the 1 source on {name}",
                        )
                elif set(status["sources"].keys()) != {"master", "test_git"}:
                    raise Exception(  # pylint: disable=broad-exception-raised
                        f"Not seeing the 2 sources on {name}: {status['sources'].keys()}",
                    )
            return True
        LOG.warning("%i, %s: %s", r.status_code, r.status, r.text)
        raise Exception(  # pylint: disable=broad-exception-raised
            f"Not having a 200 status: {r.status_code}",
        )

    utils.retry_timeout(what, timeout=10, interval=1)


@pytest.fixture(scope="package")
def composition(request):
    """Fixture that will wait that the composition is started, used for all the tests."""
    del request
    for slave in ("api", "slave", "slave-others"):
        path = os.path.join("/config", slave)
        os.makedirs(path, exist_ok=True)
        os.chown(path, 33, 0)
    utils.wait_url("http://api:8080/scm/c2c/health_check?max_level=2")
    wait_slaves()


@pytest.fixture
def app_connection(composition: None):  # pylint: disable=redefined-outer-name
    """Fixture that returns a connection to a running batch container."""
    del composition
    return Connection(base_url="http://api:8080/scm/", origin="http://example.com/")
