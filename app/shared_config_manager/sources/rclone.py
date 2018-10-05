from .base import BaseSource

import os


class RcloneSource(BaseSource):
    def __init__(self, id_, config, is_master):
        super().__init__(id_, config, is_master)
        self._setup_config(config['config'])

    def _do_refresh(self):
        os.makedirs(self.get_path(), exist_ok=True)
        cmd = ['rclone', 'sync', '--verbose', '--config', self._config_path()]
        if 'excludes' in self._config:
            cmd += ['--exclude=' + exclude for exclude in self._config['excludes']]

        cmd += ["remote:" + self.get_config().get('sub_dir', ''), self.get_path()]
        self._exec(*cmd)

    def _config_path(self):
        return os.path.join(os.environ['HOME'], '.config', 'rclone', self.get_id() + '.conf')

    def _setup_config(self, config):
        path = self._config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as file_:
            file_.write("[remote]\n")
            file_.write(config)
