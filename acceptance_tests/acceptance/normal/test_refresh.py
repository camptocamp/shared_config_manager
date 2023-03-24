import hashlib
import hmac
import json as json_module
from typing import Any, Dict

from c2cwsgiutils.acceptance.connection import CacheExpected, Connection


def test_ok(app_connection: Connection):
    answer = app_connection.get_json("1/refresh/test_git", headers={"X-Scm-Secret": "changeme"})
    assert answer == {"status": 200}


def test_no_auth(app_connection: Connection):
    app_connection.get(
        "1/refresh/test_git",
        expected_status=302,
        allow_redirects=False,
        cache_expected=CacheExpected.DONT_CARE,
    )


def test_bad_id(app_connection: Connection):
    app_connection.get(
        "1/refresh/unknown",
        headers={"X-Scm-Secret": "changeme"},
        expected_status=404,
        cache_expected=CacheExpected.DONT_CARE,
    )


def _trigger(app_connection: Connection, url: str, json: Dict[str, Any], headers: Dict[str, str]):
    json = json_module.dumps(json).encode("utf-8")
    return app_connection.post_json(
        url,
        data=json,
        headers={
            **{
                "X-Hub-Signature-256": "sha256="
                + hmac.new(
                    key=b"changeme",
                    msg=json,
                    digestmod=hashlib.sha256,
                ).hexdigest(),
            },
            **headers,
        },
    )


def test_webhook(app_connection: Connection):
    answer = _trigger(
        app_connection,
        "1/refresh/test_git",
        json={
            "ref": "refs/heads/master"
            # the rest is ignored
        },
        headers={"X-GitHub-Event": "push"},
    )

    assert answer == {"status": 200}


def test_webhook_other_branch(app_connection: Connection):
    answer = _trigger(
        app_connection,
        "1/refresh/test_git",
        json={
            "ref": "refs/heads/other"
            # the rest is ignored
        },
        headers={"X-GitHub-Event": "push"},
    )

    assert answer == {"status": 200, "ignored": True, "reason": "Not master branch"}


def test_webhook_not_push(app_connection: Connection):
    answer = _trigger(
        app_connection,
        "1/refresh/test_git",
        {
            "ref": "refs/heads/master"
            # the rest is ignored
        },
        headers={"X-GitHub-Event": "pull_request"},
    )

    assert answer == {"status": 200, "ignored": True, "reason": "Not a push"}


def test_all(app_connection: Connection):
    answer = app_connection.get_json("1/refresh", headers={"X-Scm-Secret": "changeme"})
    assert answer == {"status": 200, "nb_refresh": 1}


def test_all_webhook(app_connection: Connection):
    answer = _trigger(
        app_connection, "1/refresh", json={"ref": "refs/heads/master"}, headers={"X-GitHub-Event": "push"}
    )
    assert answer == {"status": 200, "nb_refresh": 1}


def test_all_no_auth(app_connection: Connection):
    app_connection.get(
        "1/refresh", expected_status=302, allow_redirects=False, cache_expected=CacheExpected.DONT_CARE
    )
