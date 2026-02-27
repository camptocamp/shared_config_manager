import re

from anyio import Path

from shared_config_manager import broadcast_status
from shared_config_manager.configuration import SourceConfig
from shared_config_manager.sources.base import BaseSource


class RcloneSource(BaseSource):
    """Source that get files with rclone."""

    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        super().__init__(id_, config, is_master)

    async def refresh(self) -> None:
        await self._setup_config(self._config["config"])
        await super().refresh()

    async def _do_refresh(self) -> None:
        config_path = await self._config_path()
        was_here = await self.get_path().is_dir()
        target = self.get_path() if was_here else self.get_path().with_suffix(".tmp")
        await target.mkdir(parents=True, exist_ok=True)
        cmd = ["rclone", "sync", "--verbose", "--config", str(config_path)]
        if "excludes" in self._config:
            cmd += ["--exclude=" + exclude for exclude in self._config["excludes"]]

        cmd += ["remote:" + self.get_config().get("sub_dir", ""), str(target)]
        self._exec(*cmd)
        if not was_here:
            await target.rename(self.get_path())

    async def _config_path(self) -> Path:
        return await Path.home() / ".config" / "rclone" / f"{self.get_id()}.conf"

    async def _setup_config(self, config: str) -> None:
        path = await self._config_path()
        await path.parent.mkdir(parents=True, exist_ok=True)
        async with await path.open("w", encoding="utf-8") as file_:
            await file_.write("[remote]\n")
            await file_.write(config)

    async def get_stats(self) -> broadcast_status.SourceStatus:
        stats = await super().get_stats()
        stats["config"] = _filter_config(stats["config"])
        return stats


CONFIG_FILTER_RE = re.compile(r"((?:access_key_id|secret_access_key) *= ).*")


def _filter_config(config: str) -> str:
    return CONFIG_FILTER_RE.sub("\\1???", config)
