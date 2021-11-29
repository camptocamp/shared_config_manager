import base64
import json
import logging
import os
import tempfile

from . import mode
from .base import BaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class FileSource(BaseSource):
    def get_stats(self):
        stats = super().get_stats()
        stats_path = os.path.join(self.get_path(), ".gitstats")
        if os.path.isfile(stats_path):
            with open(stats_path, "r") as gitstats:
                stats.update(json.load(gitstats))
        return stats
