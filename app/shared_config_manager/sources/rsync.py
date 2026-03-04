from anyio import Path

from shared_config_manager.sources.ssh import SshBaseSource


class RsyncSource(SshBaseSource):
    """Source that get files with rsync."""

    async def _do_refresh(self) -> None:
        await self._copy(Path(self._config["source"]))
