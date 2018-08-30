import logging
import os
import pathlib

LOG = logging.getLogger(__name__)


class BaseEngine(object):
    def __init__(self, config, glob):
        self._config = config
        self._glob = glob
        if self._config.get('environment_variables', False):
            self._data = dict(os.environ)
            self._data.update(config.get('data', {}))
        else:
            self._data = config.get('data', {})

    def evaluate(self, path):
        for path in pathlib.Path(path).glob(self._glob):
            LOG.info("Evaluating template: %s", path)
            self._evaluate_file(str(path))

    def _evaluate_file(self, path):
        pass
