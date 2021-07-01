import base64
import json
import logging
import os
import tempfile

from . import mode
from .ssh import SshBaseSource

TEMP_DIR = tempfile.gettempdir()
LOG = logging.getLogger(__name__)


class GitSource(SshBaseSource):
    def _do_refresh(self):
        self._checkout()
        self._copy(self._copy_dir(), excludes=[".git"])
        stats = dict(hash=self._get_hash(), tags=self._get_tags())
        with open(os.path.join(self.get_path(), ".gitstats"), "w") as gitstats:
            json.dump(stats, gitstats)

    def _checkout(self):
        cwd = self._clone_dir()
        repo = self._get_repo()
        branch = self.get_branch()
        if os.path.isdir(os.path.join(cwd, ".git")):
            LOG.info("Fetching a new version of %s", repo)
            self._exec("git", "fetch", "--depth=1", "origin", branch, cwd=cwd)
            self._exec("git", "checkout", branch, cwd=cwd)
            self._exec("git", "reset", "--hard", f"origin/{branch}", cwd=cwd)
        elif self._do_sparse():
            LOG.info("Cloning %s (sparse)", repo)
            self._exec("git-sparse-clone", repo, branch, cwd, self._config["sub_dir"], cwd=TEMP_DIR)
        else:
            LOG.info("Cloning %s", repo)
            os.makedirs(os.path.dirname(cwd), exist_ok=True)
            command = ["git", "clone", f"--branch={branch}", "--depth=1", repo, os.path.basename(cwd)]
            self._exec(*command, cwd=TEMP_DIR)

    def _get_repo(self):
        return self._config["repo"]

    def _clone_dir(self):
        if self._do_sparse():
            return os.path.join(TEMP_DIR, self.get_id())
        else:
            # The directory we clone into is not fct(id), but in function of the repository and the
            # branch. That way, if two sources are other sub-dirs of the same repo, we clone it only once.
            encoded_repo = base64.urlsafe_b64encode(self._get_repo().encode("utf-8")).decode("utf-8")
            return os.path.join(TEMP_DIR, encoded_repo)

    def _do_sparse(self):
        return "sub_dir" in self._config and self._config.get("sparse", True)

    def _copy_dir(self):
        sub_dir = self._config.get("sub_dir")
        if sub_dir is None:
            return self._clone_dir()
        else:
            return os.path.join(self._clone_dir(), sub_dir)

    def get_stats(self):
        stats = super().get_stats()
        stats_path = os.path.join(self.get_path(), ".gitstats")
        if os.path.isfile(stats_path):
            with open(stats_path) as gitstats:
                stats.update(json.load(gitstats))
        return stats

    def _get_hash(self):
        return self._exec("git", "rev-parse", "HEAD", cwd=self._clone_dir())

    def _get_tags(self):
        out = self._exec("git", "tag", "--points-at", "HEAD", cwd=self._clone_dir())
        if out == "":
            return []
        return out.split("\n")

    def get_branch(self):
        return str(self._config.get("branch", "master"))

    def delete(self):
        super().delete()
        if mode.is_master():
            self._exec("rm", "-rf", self._clone_dir())
