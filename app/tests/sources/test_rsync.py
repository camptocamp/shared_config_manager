import os

from shared_config_manager import sources


def test_rsync():
    source = sources._create_source('test_rsync', {
        'type': 'rsync',
        'source': '/app/tests/sources'
    })
    source.refresh()
    assert os.path.isfile('/config/test_rsync/test_rsync.py')
