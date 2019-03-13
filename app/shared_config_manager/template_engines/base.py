import logging
import os
import pathlib

LOG = logging.getLogger(__name__)
ENV_PREFIXES = os.environ.get('SCM_ENV_PREFIXES', 'MUTUALIZED_').split(':')


class BaseEngine(object):
    def __init__(self, config, glob):
        self._config = config
        self._glob = glob
        if self._config.get('environment_variables', False):
            self._data = _filter_env(os.environ)
            self._data.update(config.get('data', {}))
        else:
            self._data = config.get('data', {})

    def evaluate(self, path):
        for path in pathlib.Path(path).glob(self._glob):
            LOG.info("Evaluating template: %s", path)
            try:
                self._evaluate_file(str(path))
            except Exception:
                LOG.warning("Failed applying the %s template: %s",
                            self._config['type'], str(path), exc_info=True)

    def _evaluate_file(self, path):
        pass

    def get_type(self):
        return self._config['type']

    def get_stats(self, stats):
        if self._config.get('environment_variables', False):
            stats['environment_variables'] = _filter_env(os.environ)


def _filter_env(env):
    result = {}
    for key, value in env.items():
        if any(key.startswith(i) for i in ENV_PREFIXES):
            result[key] = value
    return result
