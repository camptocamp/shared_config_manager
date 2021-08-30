import subprocess

from shared_config_manager.template_engines.base import BaseEngine


class ShellEngine(BaseEngine):
    def __init__(self, source_id, config):
        super().__init__(source_id, config, "tmpl")

    def _evaluate_file(self, src_path, dst_path):
        with open(src_path, encoding="utf-8") as input_, open(dst_path, "w", encoding="utf-8") as output:
            subprocess.check_call(["envsubst"], stdin=input_, stdout=output, env=self._data)
