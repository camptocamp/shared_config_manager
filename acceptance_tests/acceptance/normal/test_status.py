from pprint import pformat

from c2cwsgiutils.acceptance.connection import Connection


def test_all(app_connection: Connection):
    stats = app_connection.get_json("1/status", headers={"X-Scm-Secret": "changeme"})
    print(f"stats={pformat(stats)}")
    assert len(stats["slaves"]) == 4, stats["slaves"].keys()
    assert stats["slaves"]["api"]["sources"] == stats["slaves"]["slave"]["sources"]
    assert set(stats["slaves"]["slave-others"]["sources"].keys()) == {"master"}


def test_master(app_connection: Connection):
    stats = app_connection.get_json("1/status/master", headers={"X-Scm-Secret": "changeme"})
    print(f"stats={pformat(stats)}")
    assert len(stats["statuses"]) == 1


def test_other(app_connection: Connection):
    stats = app_connection.get_json("1/status/test_git", headers={"X-Scm-Secret": "changeme"})
    print(f"stats={pformat(stats)}")
    assert len(stats["statuses"]) == 2, stats["statuses"]
    status = stats["statuses"][0]
    assert len(status["template_engines"]) == 1
    assert "environment_variables" in status["template_engines"][0]
    assert "TEST_ENV" in status["template_engines"][0]["environment_variables"]
    assert status["template_engines"][0]["environment_variables"]["TEST_ENV"] == "42", status[
        "template_engines"
    ][0]["environment_variables"]
    assert status["template_engines"][0]["environment_variables"]["TEST_KEY"] == "•••", status[
        "template_engines"
    ][0]["environment_variables"]
    assert set(status["tags"]) == {"1.0.0", "otherTag"}
