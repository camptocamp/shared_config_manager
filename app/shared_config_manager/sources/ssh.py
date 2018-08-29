import fileinput
import os
from pathlib import Path


from .base import BaseSource


class SshBaseSource(BaseSource):
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

    def get_stats(self):
        stats = super().get_stats()
        if 'ssh_key' in stats:
            del stats['ssh_key']
        return stats

    def delete(self):
        super().delete()
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
