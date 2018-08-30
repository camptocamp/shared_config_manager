from .base import BaseEngine
import subprocess


class ShellEngine(BaseEngine):
    def __init__(self, config):
        super().__init__(config, '**/*.tmpl')

    def _evaluate_file(self, path):
        with open(path) as input, open(path[:-5], 'w') as output:
            subprocess.check_call(['envsubst'], stdin=input, stdout=output, env=self._data)
