from pathlib import Path

from shared_config_manager.sources import registry


def test_rsync() -> None:
    source = registry._create_source(
        "test_rsync",
        {"type": "rsync", "source": "/app/tests/sources", "excludes": ["test_git.py"]},
    )
    source.refresh()
    assert Path("/config/test_rsync/test_rsync.py").is_file()
    assert not Path("/config/test_rsync/test_git.py").is_file()
