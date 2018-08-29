import logging
from pyramid.httpexceptions import HTTPForbidden
import shutil
import subprocess
import os

LOG = logging.getLogger(__name__)
TARGET = "/config"
MASTER_TARGET = "/master_config"


class BaseSource(object):
    def __init__(self, id_, config, is_master):
        self._id = id_
        self._config = config
        self._is_master = is_master

    def refresh(self):
        pass

    def _copy(self, source):
        os.makedirs(self.get_path(), exist_ok=True)
        self._exec('rsync', '--archive', '--delete', '--exclude=.git', '--verbose',
                   source + '/', self.get_path())

    def delete_target_dir(self):
        dest = self.get_path()
        if os.path.isdir(dest):
            shutil.rmtree(dest)

    def get_path(self):
        if 'target_dir' in self._config:
            target_dir = self._config['target_dir']
            if target_dir.startswith('/'):
                return target_dir
            else:
                return os.path.join(MASTER_TARGET if self._is_master else TARGET, target_dir)
        else:
            return os.path.join(MASTER_TARGET if self._is_master else TARGET, self.get_id())

    def get_id(self):
        return self._id

    def validate_key(self, key):
        if key != self._config['key']:
            raise HTTPForbidden("Invalid key")

    def is_master(self):
        return self._is_master

    def get_stats(self):
        stats = dict(self._config)
        del stats['key']
        return stats

    def get_config(self):
        return self._config

    def get_type(self):
        return self._config['type']

    def delete(self):
        self.delete_target_dir()

    def _exec(self, *args, **kwargs):
        try:
            LOG.debug("Running: " + ' '.join(args))
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, **kwargs)
            if output:
                output = output.decode("utf-8").strip()
                LOG.debug(output)
            return output
        except subprocess.CalledProcessError as e:
            LOG.error(e.output.decode("utf-8").strip())
            raise
