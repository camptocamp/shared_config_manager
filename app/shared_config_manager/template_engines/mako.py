import mako.template
from shared_config_manager.configuration import TemplateEnginesConfig
from shared_config_manager.template_engines.base import BaseEngine


class MakoEngine(BaseEngine):
    def __init__(self, source_id: str, config: TemplateEnginesConfig) -> None:
        super().__init__(source_id, config, "mako")

    def _evaluate_file(self, src_path: str, dst_path: str) -> None:
        template = mako.template.Template(filename=src_path)
        with open(dst_path, "w", encoding="utf-8") as output:
            output.write(template.render(**self._data))
