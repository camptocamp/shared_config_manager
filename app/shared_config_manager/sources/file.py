import base64
import json
import logging
import os
import tempfile


from shared_config_manager.sources.base import BaseSource
from shared_config_manager.sources import reload_master_config
from inotify_simple import INotify, flags

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class FileSource(BaseSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        inotify = INotify()
        inotify.add_watch(self.get_path(), flags.CREATE | flags.DELETE | flags.MODIFY)
        for _ in inotify.read():
            reload_master_config()
