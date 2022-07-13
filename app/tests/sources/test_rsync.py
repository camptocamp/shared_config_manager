import os

from shared_config_manager.sources import registry


def test_rsync():
    source = registry._create_source(
        "test_rsync", {"type": "rsync", "source": "/app/tests/sources", "excludes": ["test_git.py"]}
    )
    source.refresh()
    assert os.path.isfile("/config/test_rsync/test_rsync.py")
    assert not os.path.isfile("/config/test_rsync/test_git.py")
