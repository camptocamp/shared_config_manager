from pathlib import Path

import pytest

from shared_config_manager.sources import base, registry


@pytest.mark.asyncio
async def test_rsync() -> None:
    await base.init()
    source = registry._create_source(
        "test_rsync",
        {"type": "rsync", "source": "/app/tests/sources", "excludes": ["test_git.py"]},
    )
    await source.refresh()
    assert Path("/config/test_rsync/test_rsync.py").is_file()
    assert not Path("/config/test_rsync/test_git.py").is_file()
