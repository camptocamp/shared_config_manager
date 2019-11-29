from .base import BaseEngine
import subprocess


class ShellEngine(BaseEngine):
    def __init__(self, source_id, config):
        super().__init__(source_id, config, 'tmpl')

    def _evaluate_file(self, src_path, dst_path):
        with open(src_path) as input, open(dst_path, 'w') as output:
            subprocess.check_call(['envsubst'], stdin=input, stdout=output, env=self._data)
