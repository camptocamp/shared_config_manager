from shared_config_manager.sources.ssh import SshBaseSource


class RsyncSource(SshBaseSource):
    """Source that get files with rsync."""

    def _do_refresh(self) -> None:
        self._copy(self._config["source"])
