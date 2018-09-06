import logging
import os
import pathlib

LOG = logging.getLogger(__name__)
REMOVED_ENV = {
    'PATH',
    'HOME',
    'DEVELOPMENT',
    'COVERAGE',
    'HOSTNAME',
    'MASTER_CONFIG',
    'PKG_CONFIG_ALLOW_SYSTEM_LIBS',
    'STATS_VIEW',
    'TERM',
    'LANG',
    'PWD',
    'SERVER_SOFTWARE',
    'SHLVL',
    '_'
}
REMOVED_ENV_PREFIX = [
    'C2C_',
    'GUNICORN_',
    'LOG_'
]
REMOVED_ENV_SUFFIX = [
    '_LOG_LEVEL'
]


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

    def get_stats(self, stats):
        if self._config.get('environment_variables', False):
            stats['env'] = _filter_env(os.environ)


def _filter_env(env):
    result = {}
    for key, value in env.items():
        if key not in REMOVED_ENV and \
                not any(key.startswith(i) for i in REMOVED_ENV_PREFIX) and \
                not any(key.endswith(i) for i in REMOVED_ENV_SUFFIX):
            result[key] = value
    return result
