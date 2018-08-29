import logging
import os
import tempfile

from .ssh import SshBaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class GitSource(SshBaseSource):
    def refresh(self):
        self._checkout()
        self._copy(self._copy_dir(), excludes=['.git'])

    def _checkout(self):
        dir = self._clone_dir()
        repo = self._config['repo']
        branch = self.get_branch()
        if os.path.isdir(os.path.join(dir, '.git')):
            LOG.info("Fetching a new version of %s", repo)
            self._exec('git', 'fetch', '--depth', '1', 'origin', branch, cwd=dir)
            self._exec('git', 'checkout', branch, cwd=dir)
            self._exec('git', 'reset', '--hard', f'origin/{branch}', cwd=dir)
        elif 'sub_dir' in self._config:
            LOG.info("Cloning %s (sparse)", repo)
            self._exec('/app/git_sparse_clone', repo, branch, self.get_id(), self._config['sub_dir'],
                       cwd=TEMP_DIR)
        else:
            LOG.info("Cloning %s", repo)
            command = ['git', 'clone', '-b', branch, '--depth', '1', repo, self.get_id()]
            self._exec(*command, cwd=TEMP_DIR)

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
