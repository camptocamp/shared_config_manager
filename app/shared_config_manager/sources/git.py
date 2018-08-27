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
        self._setup_key(config.get('ssh_key'))

    def _setup_key(self, key):
        if key is None:
            return
        git_path = os.path.join(str(Path.home()), '.git')
        key_path = os.path.join(git_path, self.get_id()) + '.key'
        was_here = os.path.isfile(key_path)
        with open(key_path, 'w') as key:
            key.write(key)

        if not was_here:
            with open(os.path.join(git_path, 'config'), 'a') as config:
                config.write(f'\nIdentityFile {key_path}\n')

    def refresh(self):
        self._checkout()
        self._copy(self._copy_dir())

    def _checkout(self):
        dir = self._clone_dir()
        repo = self._config['repo']
        branch = self._config.get('branch', 'master')
        if os.path.isdir(os.path.join(dir, '.git')):
            LOG.info("Fetching a new version of %s", repo)
            self._exec('git', 'fetch', cwd=dir)
            self._exec('git', 'checkout', branch, cwd=dir)
            self._exec('git', 'reset', '--hard', f'origin/{branch}', cwd=dir)
        else:
            LOG.info("Cloning %s", repo)
            command = ['git', 'clone', '-b', branch, repo, self.get_id()]
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
        return os.path.join(TEMP_DIR, self.get_id())

    def _copy_dir(self):
        sub_dir = self._config.get('sub_dir')
        if sub_dir is None:
            return self._clone_dir()
        else:
            return os.path.join(self._clone_dir(), sub_dir)

    def get_stats(self):
        stats = super().get_stats()
        stats['hash'] = self._get_hash()
        return stats

    def _get_hash(self):
        return self._exec('git', 'rev-parse', 'HEAD', cwd=self._clone_dir()).decode("utf-8").strip()
