import copy
import logging
import os
import pathlib
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, cast

import requests
from c2cwsgiutils import stats
from pyramid.httpexceptions import HTTPForbidden

from shared_config_manager import template_engines
from shared_config_manager.configuration import SourceConfig, SourceStatus
from shared_config_manager.sources import mode

LOG = logging.getLogger(__name__)
TARGET = os.environ.get("TARGET", "/config")
MASTER_TARGET = os.environ.get("MASTER_TARGET", "/master_config")


class BaseSource:
    def __init__(self, id_: str, config: SourceConfig, is_master: bool, default_key: Optional[str]) -> None:
        self._id = id_
        self._config = config
        self._is_master = is_master
        self._is_loaded = False
        self._template_engines = [
            template_engines.create_engine(self.get_id(), engine_conf)
            for engine_conf in config.get("template_engines", [])
        ]
        if "key" not in config and default_key is not None:
            config["key"] = default_key

    def refresh_or_fetch(self) -> None:
        if mode.is_master():
            self.refresh()
        else:
            self.fetch()

    def refresh(self) -> None:
        LOG.info("Doing a refresh of %s", self.get_id())
        try:
            self._is_loaded = False
            with stats.timer_context(["source", self.get_id(), "refresh"]):
                self._do_refresh()
            self._eval_templates()
        except Exception:
            LOG.exception("Error with source %s", self.get_id())
            stats.increment_counter(["source", self.get_id(), "error"])
            raise
        finally:
            self._is_loaded = True

    def _eval_templates(self) -> None:
        if mode.is_master_with_slaves():
            # masters with slaves don't need to evaluate templates
            return
        # We get the list of files only once to avoid consecutive template engines eating the output of
        # the previous template engines. This method is always called with a root_dir that is clean from
        # all the files that are created by template engines (see the --delete rsync flag in
        # BaseSource._copy).
        root_dir = self.get_path()
        files = [os.path.relpath(str(p), root_dir) for p in pathlib.Path(root_dir).glob("**/*")]

        for engine in self._template_engines:
            with stats.timer_context(["source", self.get_id(), "template", engine.get_type()]):
                engine.evaluate(root_dir, files)

    def fetch(self) -> None:
        try:
            self._is_loaded = False
            with stats.timer_context(["source", self.get_id(), "fetch"]):
                self._do_fetch()
            self._eval_templates()
        except Exception:
            LOG.exception("Error with source %s", self.get_id())
            stats.increment_counter(["source", self.get_id(), "error"])
            raise
        finally:
            self._is_loaded = True

    def _do_refresh(self) -> None:
        pass

    def _do_fetch(self) -> None:
        path = self.get_path()
        url = mode.get_fetch_url(self.get_id(), self._config["key"])
        while True:
            try:
                LOG.info("Doing a fetch of %s", self.get_id())
                response = requests.get(url, stream=True)
                response.raise_for_status()
                if os.path.exists(path):
                    shutil.rmtree(path)
                os.makedirs(path, exist_ok=True)
                with subprocess.Popen(
                    [
                        "tar",
                        "--extract",
                        "--gzip",
                        "--no-same-owner",
                        "--no-same-permissions",
                        "--touch",
                        "--no-overwrite-dir",
                    ],
                    cwd=path,
                    stdin=subprocess.PIPE,
                ) as tar:
                    shutil.copyfileobj(response.raw, tar.stdin)  # type: ignore
                    tar.stdin.close()  # type: ignore
                    assert tar.wait() == 0
                return
            except Exception as exception:
                stats.increment_counter(["source", self.get_id(), "fetch_error"])
                LOG.warning(
                    "Error fetching the source %s from the master (will retry in 1s): %s",
                    self.get_id(),
                    str(exception),
                )
                time.sleep(1)

    def _copy(self, source: str, excludes: Optional[List[str]] = None) -> None:
        os.makedirs(self.get_path(), exist_ok=True)
        cmd = [
            "rsync",
            "--recursive",
            "--links",
            "--devices",
            "--specials",
            "--delete",
            "--verbose",
            "--checksum",
        ]
        if excludes is not None:
            cmd += ["--exclude=" + exclude for exclude in excludes]
        if "excludes" in self._config:
            cmd += ["--exclude=" + exclude for exclude in self._config["excludes"]]
        cmd += [source + "/", self.get_path()]
        with stats.timer_context(["source", self.get_id(), "copy"]):
            self._exec(*cmd)

    def delete_target_dir(self) -> None:
        dest = self.get_path()
        LOG.info("Deleting target dir %s", dest)
        if os.path.isdir(dest):
            shutil.rmtree(dest)

    def get_path(self) -> str:
        if "target_dir" in self._config:
            target_dir = self._config["target_dir"]
            if target_dir.startswith("/"):
                return target_dir
            else:
                return os.path.join(MASTER_TARGET if self._is_master else TARGET, target_dir)
        else:
            return os.path.join(MASTER_TARGET if self._is_master else TARGET, self.get_id())

    def get_id(self) -> str:
        return self._id

    def validate_key(self, key: str) -> None:
        if key != self._config["key"]:
            raise HTTPForbidden("Invalid key")

    def is_master(self) -> bool:
        return self._is_master

    def get_stats(self) -> SourceStatus:
        config_copy = copy.deepcopy(self._config)
        del config_copy["key"]
        stats_ = cast(SourceStatus, config_copy)
        for template_stats, template_engine in zip(
            stats_.get("template_engines", []), self._template_engines
        ):
            template_engine.get_stats(template_stats)

            BaseSource._hide_sensitive(template_stats.get("data"))
            BaseSource._hide_sensitive(template_stats.get("environment_variables"))
        return stats_

    def get_config(self) -> SourceConfig:
        return self._config

    def get_type(self) -> str:
        return self._config["type"]

    def delete(self) -> None:
        self.delete_target_dir()

    @staticmethod
    def _exec(*args: Any, **kwargs: Any) -> str:
        try:
            args_ = list(map(str, args))
            LOG.debug("Running: %s", " ".join(args_))
            output: str = (
                subprocess.run(
                    args_,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=dict(os.environ),
                    **kwargs,
                )
                .stdout.decode("utf-8")
                .strip()
            )
            if output:
                LOG.debug(output)
            return output
        except subprocess.CalledProcessError as exception:
            LOG.error(exception.output.decode("utf-8").strip())
            raise

    def is_loaded(self) -> bool:
        return self._is_loaded

    @staticmethod
    def _hide_sensitive(data: Optional[Dict[str, str]]) -> None:
        if data is None:
            return
        for key in list(data.keys()):
            k = key.upper()
            if "KEY" in k or "PASSWORD" in k or "SECRET" in k:
                data[key] = "xxx"
