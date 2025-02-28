import re
from pathlib import Path

from shared_config_manager.configuration import SourceConfig, SourceStatus
from shared_config_manager.sources.base import BaseSource


class RcloneSource(BaseSource):
    """Source that get files with rclone."""

    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        super().__init__(id_, config, is_master)
        self._setup_config(config["config"])

    def _do_refresh(self) -> None:
        was_here = self.get_path().is_dir()
        target = self.get_path() if was_here else self.get_path().with_suffix(".tmp")
        target.mkdir(parents=True, exist_ok=True)
        cmd = ["rclone", "sync", "--verbose", "--config", str(self._config_path())]
        if "excludes" in self._config:
            cmd += ["--exclude=" + exclude for exclude in self._config["excludes"]]

        cmd += ["remote:" + self.get_config().get("sub_dir", ""), str(target)]
        self._exec(*cmd)
        if not was_here:
            target.rename(self.get_path())

    def _config_path(self) -> Path:
        return Path.home() / ".config" / "rclone" / f"{self.get_id()}.conf"

    def _setup_config(self, config: str) -> None:
        path = self._config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file_:
            file_.write("[remote]\n")
            file_.write(config)

    def get_stats(self) -> SourceStatus:
        stats = super().get_stats()
        stats["config"] = _filter_config(stats["config"])
        return stats


CONFIG_FILTER_RE = re.compile(r"((?:access_key_id|secret_access_key) *= ).*")


def _filter_config(config: str) -> str:
    return CONFIG_FILTER_RE.sub("\\1???", config)
