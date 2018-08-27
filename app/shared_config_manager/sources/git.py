import fileinput
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from .base import BaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class GitSource(BaseSource):
    def __init__(self, id_, config, is_master):
        super().__init__(id_, config, is_master)
        self._setup_key(config.get('ssh_key'))

    def _setup_key(self, ssh_key):
        if ssh_key is None:
            return
        ssh_path = os.path.join(str(Path.home()), '.ssh')
        os.makedirs(ssh_path)
        key_path = os.path.join(ssh_path, self.get_id()) + '.key'
        was_here = os.path.isfile(key_path)
        with open(key_path, 'w') as ssh_key_file:
            ssh_key_file.write(ssh_key)
        os.chmod(key_path, 0o700)

        if not was_here:
            with open(os.path.join(ssh_path, 'config'), 'a') as config:
                config.write(f'IdentityFile {key_path}\n')

    def refresh(self):
        self._checkout()
        self._copy(self._copy_dir())

    def _checkout(self):
        dir = self._clone_dir()
        repo = self._config['repo']
        branch = self.get_branch()
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
                output = output.decode("utf-8").strip()
                LOG.debug(output)
            return output
        except subprocess.CalledProcessError as e:
            LOG.error(e.output.decode("utf-8").strip())
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
        return self._exec('git', 'rev-parse', 'HEAD', cwd=self._clone_dir())

    def get_branch(self):
        return self._config.get('branch', 'master')

    def delete(self):
        super().delete()
        self._exec('rm', '-rf', self._clone_dir())
        ssh_key = self._config.get('ssh_key')
        if ssh_key is not None:
            ssh_path = os.path.join(str(Path.home()), '.ssh')
            key_path = os.path.join(ssh_path, self.get_id()) + '.key'
            if os.path.isfile(key_path):
                os.remove(key_path)
                with fileinput.input(os.path.join(ssh_path, 'config'), inplace=True) as config:
                    for line in config:
                        if line != f'IdentityFile {key_path}\n':
                            print(line, end='')
