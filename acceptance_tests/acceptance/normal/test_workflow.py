# pylint: disable=unspecified-encoding

import os
import subprocess
import time

import pytest
import requests
from c2cwsgiutils.acceptance.connection import Connection

from acceptance import get_hash, wait_sync


@pytest.fixture
def git_source(app_connection: Connection):
    with open("/repos/master/shared_config_manager.yaml", "a") as config:
        config.write(
            """\
  other:
    type: git
    repo: /repos/other
    tags: ['others']
    template_engines:
      - type: mako
        data:
          param: world
""",
        )

    subprocess.check_call(
        """
    set -eaux
    cd /repos

    cd master
    git commit -a -m "Added other"
    cd ..

    git init other
    cd other
    echo -n 'content ${param}' > config.txt.mako
    git add config.txt.mako
    git commit -a -m "Initial commit"
    """,
        shell=True,
    )
    time.sleep(0.1)

    master_hash = get_hash("/repos/master")
    other_hash = get_hash("/repos/other")

    response = requests.get("http://api:8080/scm/1/refresh/master", headers={"X-Scm-Secret": "changeme"})
    assert response.ok

    wait_sync(app_connection, "master", master_hash)
    wait_sync(app_connection, "other", other_hash)

    yield "/repos/other"

    subprocess.check_call(
        """
    set -eaux
    cd /repos
    rm -rf other

    cd master
    git reset --hard HEAD~1
    """,
        shell=True,
    )
    time.sleep(0.1)

    app_connection.get_json("1/refresh/master", headers={"X-Scm-Secret": "changeme"})
    wait_sync(app_connection, "other", None)
    time.sleep(0.1)

    for slave in ("api", "slave"):
        assert not os.path.exists(os.path.join("/config", slave, "other"))


def test_ok(app_connection, git_source) -> None:  # pylint: disable=redefined-outer-name
    time.sleep(0.1)

    for slave in ("api", "slave"):
        assert slave in os.listdir("/config")
        assert "other" in os.listdir(os.path.join("/config", slave))
        assert "config.txt" in os.listdir(os.path.join("/config", slave, "other"))
        with open(os.path.join("/config", slave, "other", "config.txt")) as config:
            assert config.read() == "content world"

    subprocess.check_call(
        f"""
    set -eaux
    cd {git_source}
    echo -n "content modified" > config.txt.mako
    git commit --all --message="Second commit"
    """,
        shell=True,
    )
    time.sleep(0.1)

    hash_ = get_hash(git_source)
    app_connection.get_json("1/refresh/other", headers={"X-Scm-Secret": "changeme"})
    wait_sync(app_connection, "other", hash_)
    time.sleep(0.1)

    for slave in ("api", "slave"):
        with open(os.path.join("/config", slave, "other", "config.txt")) as config:
            assert config.read() == "content modified"
