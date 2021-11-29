import logging
import tempfile

import inotify.adapters

from shared_config_manager.sources.base import BaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class FileSource(BaseSource):
    def __init__(self, *args, **kwargs):
        # To avoid circular import
        from shared_config_manager.sources import reload_master_config

        super().__init__(*args, **kwargs)
        inotify_ = inotify.adapters.Inotify()
        inotify_.add_watch(self.get_path())
        for _, type_names, path, filename in inotify_.event_gen(yield_nones=False):
            LOG.debug("Inotify event: %s / %s: [%s]", path, filename, ",".join(type_names))
            reload_master_config()
