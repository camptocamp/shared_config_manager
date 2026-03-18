import os

from anyio import Path

from shared_config_manager import broadcast_status
from shared_config_manager.configuration import SourceConfig
from shared_config_manager.sources.base import BaseSource


class SshBaseSource(BaseSource):
    """Source to get files from SSH server."""

    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        super().__init__(id_, config, is_master)
        self._ssh_key = config.get("ssh_key")

    async def refresh(self) -> None:
        if self._ssh_key is not None:
            await self._setup_key(self._ssh_key)
        await super().refresh()

    async def _setup_key(self, ssh_key: str) -> None:
        ssh_path = self._ssh_path()
        await ssh_path.mkdir(parents=True, exist_ok=True)
        key_path = ssh_path / f"{self.get_id()}.key"
        was_here = await key_path.is_file()
        await key_path.write_text(ssh_key, encoding="utf-8")
        await key_path.chmod(0o600)

        if not was_here:
            async with await (ssh_path / "config").open("a", encoding="utf-8") as config:
                await config.write(f"IdentityFile {key_path}\n")

    @staticmethod
    def _ssh_path() -> Path:
        return Path(os.environ["HOME"]) / ".ssh"

    async def get_stats(self) -> broadcast_status.SourceStatus:
        stats = await super().get_stats()
        stats.ssh_key = None
        return stats

    async def delete(self) -> None:
        await super().delete()
        ssh_key = self._config.get("ssh_key")
        if ssh_key is not None:
            ssh_path = self._ssh_path()
            key_path = ssh_path / (self.get_id() + ".key")
            if await key_path.is_file():
                await key_path.unlink()
                config_path = ssh_path / "config"
                content = await config_path.read_text(encoding="utf-8")
                lines = [
                    line for line in content.splitlines(keepends=True) if line != f"IdentityFile {key_path}\n"
                ]
                await config_path.write_text("".join(lines), encoding="utf-8")
