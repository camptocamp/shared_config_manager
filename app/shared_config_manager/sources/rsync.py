from .ssh import SshBaseSource


class RsyncSource(SshBaseSource):
    def _do_refresh(self):
        self._copy(self._config["source"])
