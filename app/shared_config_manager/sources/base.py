from pyramid.httpexceptions import HTTPForbidden
import shutil
import os

TARGET = "/config"
MASTER_TARGET = "/master_config"


class BaseSource(object):
    def __init__(self, config, is_master):
        self._config = config
        self._is_master = is_master

    def refresh(self):
        pass

    def _copy(self, source):
        self.delete_target_dir()
        shutil.copytree(source, self.get_path())

    def delete_target_dir(self):
        dest = self.get_path()
        if os.path.isdir(dest):
            shutil.rmtree(dest)

    def get_path(self):
        return os.path.join(MASTER_TARGET if self._is_master else TARGET, self.get_target_dir())

    def get_id(self):
        return self._config['id']

    def validate_key(self, key):
        if key != self._config['key']:
            raise HTTPForbidden("Invalid key")

    def is_master(self):
        return self._is_master

    def get_stats(self):
        stats = dict(self._config)
        del stats['key']
        return stats

    def get_target_dir(self):
        return self._config.get('target_dir', self.get_id())

    def get_config(self):
        return self._config
