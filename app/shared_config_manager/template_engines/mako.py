import mako.template  # pylint: disable=no-name-in-module,import-error

from anyio import Path

from shared_config_manager.configuration import TemplateEnginesConfig
from shared_config_manager.template_engines.base import BaseEngine


class MakoEngine(BaseEngine):
    """Mako template engine."""

    def __init__(self, source_id: str, config: TemplateEnginesConfig) -> None:
        super().__init__(source_id, config, "mako")

    async def _evaluate_file(self, src_path: Path, dst_path: Path) -> None:
        content = await src_path.read_text(encoding="utf-8")
        template = mako.template.Template(text=content)  # noqa: S702 # pylint: disable=no-member
        await dst_path.write_text(template.render(**self._data), encoding="utf-8")
