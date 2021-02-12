import subprocess
from pprint import pformat

from c2cwsgiutils.acceptance import utils


def test_all(app_connection):
    def what():
        subprocess.check_call(
            """
        set -eux
        cd /repos/master
        git show
        cd /config/
        ls -al
        find / -name master
        """,
            shell=True,
        )
        stats = app_connection.get_json("1/status/changeme")
        assert len(stats["slaves"]) == 3, stats["slaves"].keys()

    utils.retry_timeout(what, timeout=2, interval=0.1)

    stats = app_connection.get_json("1/status/changeme")
    print(f"stats={pformat(stats)}")
    assert len(stats["slaves"]) == 3, stats["slaves"].keys()
    assert stats["slaves"]["api"]["sources"] == stats["slaves"]["slave"]["sources"]
    assert set(stats["slaves"]["slave-others"]["sources"].keys()) == {"master"}


def test_master(app_connection):
    stats = app_connection.get_json("1/status/master/changeme")
    print(f"stats={pformat(stats)}")
    assert len(stats["statuses"]) == 1


def test_other(app_connection):
    stats = app_connection.get_json("1/status/test_git/changeme")
    print(f"stats={pformat(stats)}")
    assert len(stats["statuses"]) == 1, stats["statuses"]
    status = stats["statuses"][0]
    assert len(status["template_engines"]) == 1
    assert "environment_variables" in status["template_engines"][0]
    assert "TEST_ENV" in status["template_engines"][0]["environment_variables"]
    assert status["template_engines"][0]["environment_variables"]["TEST_ENV"] == "42", status[
        "template_engines"
    ][0]["environment_variables"]
    assert status["template_engines"][0]["environment_variables"]["TEST_KEY"] == "xxx", status[
        "template_engines"
    ][0]["environment_variables"]
    assert set(status["tags"]) == {"1.0.0", "otherTag"}
