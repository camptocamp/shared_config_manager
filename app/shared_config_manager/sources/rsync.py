from .ssh import SshBaseSource


class RsyncSource(SshBaseSource):
    def refresh(self):
        self._copy(self._config['source'])
