import fileinput
import os
from pathlib import Path

from shared_config_manager import broadcast_status
from shared_config_manager.configuration import SourceConfig
from shared_config_manager.sources.base import BaseSource


class SshBaseSource(BaseSource):
    """Source to get files from SSH server."""

    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        super().__init__(id_, config, is_master)
        self._setup_key(config.get("ssh_key"))

    def _setup_key(self, ssh_key: str | None) -> None:
        if ssh_key is None:
            return
        ssh_path = self._ssh_path()
        ssh_path.mkdir(parents=True, exist_ok=True)
        key_path = ssh_path / f"{self.get_id()}.key"
        was_here = key_path.is_file()
        key_path.write_text(ssh_key, encoding="utf-8")
        key_path.chmod(0o700)

        if not was_here:
            with (ssh_path / "config").open("a", encoding="utf-8") as config:
                config.write(f"IdentityFile {key_path}\n")

    @staticmethod
    def _ssh_path() -> Path:
        return Path(os.environ["HOME"]) / ".ssh"

    def get_stats(self) -> broadcast_status.SourceStatus:
        stats = super().get_stats()
        if "ssh_key" in stats:
            del stats["ssh_key"]
        return stats

    def delete(self) -> None:
        super().delete()
        ssh_key = self._config.get("ssh_key")
        if ssh_key is not None:
            ssh_path = self._ssh_path()
            key_path = ssh_path / (self.get_id() + ".key")
            if key_path.is_file():
                key_path.unlink()
                with fileinput.input(ssh_path / "config", inplace=True) as config:
                    for line in config:
                        if line != f"IdentityFile {key_path}\n":
                            print(line, end="")
