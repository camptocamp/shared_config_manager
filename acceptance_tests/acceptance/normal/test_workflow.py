import os
import pytest
import subprocess

from acceptance import wait_sync, get_hash


@pytest.yield_fixture()
def git_source(app_connection, test_repos):
    with open(os.path.join(test_repos, "master", "shared_config_manager.yaml"), "a") as config:
        config.write(
            """\
  other:
    type: git
    repo: /repos/other
    key: changeme
    tags: ['others']
    template_engines:
      - type: mako
        data:
          param: world
"""
        )

    subprocess.check_call(
        f"""
    set -e
    cd {test_repos}

    cd master
    git commit -a -m "Added other"
    cd ..

    git init other
    cd other
    echo -n 'content ${{param}}' > config.txt.mako
    git add config.txt.mako
    git commit -a -m "Initial commit"
    """,
        shell=True,
    )

    master_hash = get_hash(os.path.join(test_repos, "master"))
    other_hash = get_hash(os.path.join(test_repos, "other"))

    app_connection.get_json("1/refresh/master/changeme")

    wait_sync(app_connection, "master", master_hash)
    wait_sync(app_connection, "other", other_hash)

    yield os.path.join(test_repos, "other")

    subprocess.check_call(
        f"""
    set -e
    cd {test_repos}
    rm -rf other

    cd master
    git reset --hard HEAD~1
    """,
        shell=True,
    )

    app_connection.get_json("1/refresh/master/changeme")
    wait_sync(app_connection, "other", None)

    for slave in ("api", "slave"):
        assert not os.path.exists(os.path.join("/tmp", "slaves", slave, "other"))


def test_ok(app_connection, git_source):
    for slave in ("api", "slave"):
        with open(os.path.join("/tmp", "slaves", slave, "other", "config.txt")) as config:
            assert config.read() == "content world"

    subprocess.check_call(
        f"""
    set -e
    cd {git_source}
    echo -n "content modified" > config.txt.mako
    git commit -a -m "Second commit"
    """,
        shell=True,
    )

    hash = get_hash(git_source)
    app_connection.get_json("1/refresh/other/changeme")
    wait_sync(app_connection, "other", hash)

    for slave in ("api", "slave"):
        with open(os.path.join("/tmp", "slaves", slave, "other", "config.txt")) as config:
            assert config.read() == "content modified"
