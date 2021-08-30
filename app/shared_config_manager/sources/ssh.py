import fileinput
import os

from shared_config_manager.sources.base import BaseSource


def _patch_openshift():
    os.environ["HOME"] = "/var/www"
    try:
        with open("/etc/passwd", "a", encoding="utf-8") as passwd:
            passwd.write(f"www-data2:x:{os.getuid()}:0:www-data:/var/www:/usr/sbin/nologin\n")
    except PermissionError:
        pass  # ignored


# hack to work around an OpenShift "security"
if os.getuid() not in (33, 0):
    _patch_openshift()


class SshBaseSource(BaseSource):
    def __init__(self, id_, config, is_master, default_key):
        super().__init__(id_, config, is_master, default_key)
        self._setup_key(config.get("ssh_key"))

    def _setup_key(self, ssh_key):
        if ssh_key is None:
            return
        ssh_path = self._ssh_path()
        os.makedirs(ssh_path, exist_ok=True)
        key_path = os.path.join(ssh_path, self.get_id()) + ".key"
        was_here = os.path.isfile(key_path)
        with open(key_path, "w", encoding="utf-8") as ssh_key_file:
            ssh_key_file.write(ssh_key)
        os.chmod(key_path, 0o700)

        if not was_here:
            with open(os.path.join(ssh_path, "config"), "a", encoding="utf-8") as config:
                config.write(f"IdentityFile {key_path}\n")

    @staticmethod
    def _ssh_path():
        return os.path.join(os.environ["HOME"], ".ssh")

    def get_stats(self):
        stats = super().get_stats()
        if "ssh_key" in stats:
            del stats["ssh_key"]
        return stats

    def delete(self):
        super().delete()
        ssh_key = self._config.get("ssh_key")
        if ssh_key is not None:
            ssh_path = self._ssh_path()
            key_path = os.path.join(ssh_path, self.get_id()) + ".key"
            if os.path.isfile(key_path):
                os.remove(key_path)
                with fileinput.input(os.path.join(ssh_path, "config"), inplace=True) as config:
                    for line in config:
                        if line != f"IdentityFile {key_path}\n":
                            print(line, end="")
