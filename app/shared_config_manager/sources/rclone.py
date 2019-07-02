from .base import BaseSource

import os
import re


class RcloneSource(BaseSource):
    def __init__(self, id_, config, is_master, default_key):
        super().__init__(id_, config, is_master, default_key)
        self._setup_config(config['config'])

    def _do_refresh(self):
        was_here = os.path.isdir(self.get_path())
        target = self.get_path() + ("" if was_here else ".tmp")
        os.makedirs(target, exist_ok=True)
        cmd = ['rclone', 'sync', '--verbose', '--config', self._config_path()]
        if 'excludes' in self._config:
            cmd += ['--exclude=' + exclude for exclude in self._config['excludes']]

        cmd += ["remote:" + self.get_config().get('sub_dir', ''), target]
        self._exec(*cmd)
        if not was_here:
            os.rename(target, self.get_path())

    def _config_path(self):
        return os.path.join(os.environ['HOME'], '.config', 'rclone', self.get_id() + '.conf')

    def _setup_config(self, config):
        path = self._config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file_:
            file_.write("[remote]\n")
            file_.write(config)

    def get_stats(self):
        stats = super().get_stats()
        stats['config'] = _filter_config(stats['config'])
        return stats


CONFIG_FILTER_RE = re.compile(r'((?:access_key_id|secret_access_key) *= ).*')


def _filter_config(config):
    return CONFIG_FILTER_RE.sub("\\1???", config)
