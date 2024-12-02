# pylint: disable=unspecified-encoding

import os

import yaml
from c2cwsgiutils.acceptance.connection import Connection

from acceptance import get_hash, wait_sync


def test_ok(app_connection: Connection):
    test_git_hash = get_hash("/repos/test_git")

    # Be sure that we have the initial config (empty)
    with open("/etc/shared_config_manager/config.yaml", "w") as config_file:
        config_file.write(
            yaml.dump(
                {
                    "sources": {},
                }
            )
        )

    # Wait that's applied
    wait_sync(app_connection, "test_git", None)

    # Test if it's correctly applied (remove)
    assert not os.path.exists(os.path.join("/config", "api-file", "test_git", "test"))

    # Change the config to have one Git source config (empty)
    with open("/etc/shared_config_manager/config.yaml", "w") as config_file:
        config_file.write(
            yaml.dump(
                {
                    "sources": {
                        "test_git": {
                            "type": "git",
                            "repo": "/repos/test_git",
                            "tags": ["test"],
                            "template_engines": [{"type": "shell", "environment_variables": True}],
                        }
                    },
                }
            )
        )

    # Wait that's applied
    wait_sync(app_connection, "test_git", test_git_hash)

    # Test if the file from the source is correctily created
    with open(os.path.join("/config", "api-file", "test_git", "test")) as config:
        assert config.read() == "Hello world\n"

    # Go back to an empty config
    with open("/etc/shared_config_manager/config.yaml", "w") as config_file:
        config_file.write(yaml.dump({"sources": {}}))

    # Wait that's applied
    wait_sync(app_connection, "test_git", None)
    # Test if the file is correctly removed
    assert not os.path.exists(os.path.join("/config", "api-file", "test_git", "test"))
