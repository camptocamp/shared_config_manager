from pyramid.httpexceptions import HTTPForbidden
import shutil
import os

TARGET = "/config"
MASTER_TARGET = "/master_config"


class BaseSource(object):
    def __init__(self, config, is_master):
        self._id = config['id']
        self._key = config['key']
        self._target_dir = config.get('target_dir', self._id)
        self._is_master = is_master

    def refresh(self):
        pass

    def _copy(self, source):
        dest = self.get_path()
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(source, dest)

    def get_path(self):
        return os.path.join(MASTER_TARGET if self._is_master else TARGET, self._target_dir)

    def get_id(self):
        return self._id

    def validate_key(self, key):
        if key != self._key:
            raise HTTPForbidden("Invalid key")

    def is_master(self):
        return self._is_master
