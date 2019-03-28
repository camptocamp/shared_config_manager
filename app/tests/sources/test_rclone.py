import os

from shared_config_manager import sources


def test_rsync():
    source = sources._create_source('test_rclone', {
        'type': 'rclone',
        'config': """\
type = http
url = http://ftp.debian.org/debian/pool/main/p/p4est//
""",
        'source': 'test:',
        'excludes': ['*.deb', '*.tar.xz'],
    })
    source.refresh()
    assert os.path.isfile('/config/test_rclone/p4est_1.1-5.dsc')
    assert not os.path.isfile('/config/test_rclone/libp4est-sc-1.1_1.1-4_amd64.deb')
    assert not os.path.isfile('/config/test_rclone/p4est_1.1.orig.tar.xz')
