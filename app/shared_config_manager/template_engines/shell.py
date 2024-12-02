import subprocess  # nosec

from shared_config_manager.configuration import TemplateEnginesConfig
from shared_config_manager.template_engines.base import BaseEngine


class ShellEngine(BaseEngine):
    """Shell template engine (envsubst)."""

    def __init__(self, source_id: str, config: TemplateEnginesConfig) -> None:
        super().__init__(source_id, config, "tmpl")

    def _evaluate_file(self, src_path: str, dst_path: str) -> None:
        with open(src_path, encoding="utf-8") as input_, open(dst_path, "w", encoding="utf-8") as output:
            subprocess.run(["envsubst"], stdin=input_, stdout=output, env=self._data, check=True)  # nosec
