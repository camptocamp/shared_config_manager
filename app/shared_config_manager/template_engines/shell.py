import asyncio

from anyio import Path

from shared_config_manager.configuration import TemplateEnginesConfig
from shared_config_manager.template_engines.base import BaseEngine


class ShellEngine(BaseEngine):
    """Shell template engine (envsubst)."""

    def __init__(self, source_id: str, config: TemplateEnginesConfig) -> None:
        super().__init__(source_id, config, "tmpl")

    async def _evaluate_file(self, src_path: Path, dst_path: Path) -> None:
        content = await src_path.read_text(encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "envsubst",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            env=self._data,
        )
        stdout, _ = await proc.communicate(input=content.encode("utf-8"))
        if proc.returncode != 0:
            msg = f"envsubst failed with return code {proc.returncode}"
            raise RuntimeError(msg)
        await dst_path.write_text(stdout.decode("utf-8"), encoding="utf-8")
