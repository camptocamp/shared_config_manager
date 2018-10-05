import os

from shared_config_manager import sources


def test_rsync():
    source = sources._create_source('test_rclone', {
        'type': 'rclone',
        'config': """\
type = http
url = http://ftp.debian.org/debian/pool/main/p/python3-dateutil/
""",
        'source': 'test:',
        'excludes': ['*.deb', '*.tar.gz'],
    })
    source.refresh()
    assert os.path.isfile('/config/test_rclone/python3-dateutil_2.0+dfsg1-1.dsc')
    assert not os.path.isfile('/config/test_rclone/python3-dateutil_2.0+dfsg1-1_all.deb')
    assert not os.path.isfile('/config/test_rclone/	python3-dateutil_2.0+dfsg1.orig.tar.gz')
