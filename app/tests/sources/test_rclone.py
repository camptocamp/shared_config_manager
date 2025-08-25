from pathlib import Path

import pytest

from shared_config_manager.sources import registry


@pytest.mark.skip(reason="No more installer in the image")
def test_rsync() -> None:
    source = registry._create_source(
        "test_rclone",
        {
            "type": "rclone",
            "config": """\
type = http
url = http://ftp.debian.org/debian/pool/main/p/p4est//
""",
            "source": "test:",
            "excludes": ["*.deb", "*.tar.xz"],
        },
    )
    source.refresh()
    assert Path("/config/test_rclone/p4est_1.1-5.dsc").is_file()
    assert not Path("/config/test_rclone/libp4est-sc-1.1_1.1-4_amd64.deb").is_file()
    assert not Path("/config/test_rclone/p4est_1.1.orig.tar.xz").is_file()
