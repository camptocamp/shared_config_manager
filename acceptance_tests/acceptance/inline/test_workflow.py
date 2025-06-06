# pylint: disable=unspecified-encoding

import os

from c2cwsgiutils.acceptance.connection import Connection

from acceptance import get_hash, wait_sync


def test_ok(app_connection: Connection) -> None:
    test_git_hash = get_hash("/repos/test_git")
    wait_sync(app_connection, "test_git", test_git_hash)

    with open(os.path.join("/config", "api-inline", "test_git", "test")) as config:
        assert config.read() == "Hello world\n"
