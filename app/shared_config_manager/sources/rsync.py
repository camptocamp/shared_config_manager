from shared_config_manager.sources.ssh import SshBaseSource


class RsyncSource(SshBaseSource):
    def _do_refresh(self):
        self._copy(self._config["source"])
