import logging
import os
from pathlib import Path
import subprocess
import tempfile

from .base import BaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class GitSource(BaseSource):
    def __init__(self, config, is_master):
        super().__init__(config, is_master)
        self._repo = config['repo']
        self._setup_key(config.get('ssh_key'))
        self._branch = config.get('branch', 'master')
        self._sub_dir = config.get('sub_dir')

    def _setup_key(self, key):
        if key is None:
            return
        git_path = os.path.join(str(Path.home()), '.git')
        key_path = os.path.join(git_path, self._id) + '.key'
        with open(key_path, 'w') as key:
            key.write(self._key)

        with open(os.path.join(git_path, 'config'), 'a') as config:
            config.write(f'\nIdentityFile {key_path}\n')

    def refresh(self):
        self._checkout()
        self._copy(self._copy_dir())

    def _checkout(self):
        dir = self._clone_dir()
        if os.path.isdir(os.path.join(dir, '.git')):
            LOG.info("Fetching a new version of %s", self._repo)
            self._exec('git', 'fetch', cwd=dir)
            self._exec('git', 'checkout', self._branch, cwd=dir)
            self._exec('git', 'reset', '--hard', f'origin/{self._branch}', cwd=dir)
        else:
            LOG.info("Cloning %s", self._repo)
            command = ['git', 'clone', '-b', self._branch, self._repo, self._id]
            self._exec(*command, cwd=TEMP_DIR)

    def _exec(self, *args, **kwargs):
        try:
            LOG.debug("Running: " + ' '.join(args))
            output = subprocess.check_output(args, stderr=subprocess.STDOUT, **kwargs)
            if output:
                LOG.debug(output.decode("utf-8"))
            return output
        except subprocess.CalledProcessError as e:
            LOG.error(e.output)
            raise

    def _clone_dir(self):
        return os.path.join(TEMP_DIR, self._id)

    def _copy_dir(self):
        if self._sub_dir is None:
            return self._clone_dir()
        else:
            return os.path.join(self._clone_dir(), self._sub_dir)

    def get_stats(self):
        stats = super().get_stats()
        stats.update(dict(repo=self._repo, branch=self._branch, sub_dir=self._sub_dir, hash=self._get_hash()))
        return stats

    def _get_hash(self):
        return self._exec('git', 'rev-parse', 'HEAD', cwd=self._clone_dir()).decode("utf-8").strip()
