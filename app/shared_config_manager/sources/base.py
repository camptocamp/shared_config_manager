import copy
import logging
import os
import pathlib
import shutil
import subprocess  # nosec
import time
from typing import Any, Optional, cast

import pyramid.request
import requests
from c2cwsgiutils import broadcast
from prometheus_client import Counter, Gauge, Summary
from pyramid.httpexceptions import HTTPForbidden
from pyramid.security import Allowed

from shared_config_manager import template_engines
from shared_config_manager.configuration import SourceConfig, SourceStatus
from shared_config_manager.sources import mode

_LOG = logging.getLogger(__name__)
_TARGET = os.environ.get("TARGET", "/config")
_MASTER_TARGET = os.environ.get("MASTER_TARGET", "/master_config")
_RETRY_NUMBER = int(os.environ.get("SCM_RETRY_NUMBER", 3))
_RETRY_DELAY = int(os.environ.get("SCM_RETRY_DELAY", 1))

_REFRESH_SUMMARY = Summary("sharedconfigmanager_source_refresh", "Number of source refreshes", ["source"])
_REFRESH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_refresh_error_counter", "Number of source errors", ["source"]
)
_REFRESH_ERROR_GAUGE = Gauge(
    "sharedconfigmanager_source_refresh_error_status", "Sources in error", ["source"]
)
_TEMPLATE_SUMMARY = Summary(
    "sharedconfigmanager_source_template", "Number of template evaluations", ["source", "type"]
)
_FETCH_SUMMARY = Summary("sharedconfigmanager_source_fetch", "Number of source fetches", ["source"])
_FETCH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_fetch_error_counter", "Number of source errors", ["source"]
)
_FETCH_ERROR_GAUGE = Gauge("sharedconfigmanager_source_fetch_error_status", "Sources in error", ["source"])
_DO_FETCH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_do_fetch_error", "Number of source fetch errors", ["source"]
)
_COPY_SUMMARY = Summary("sharedconfigmanager_source_copy", "Number of source copies", ["source"])


class BaseSource:
    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        self._id = id_
        self._config = config
        self._is_master = is_master
        self._is_loaded = False
        self._template_engines = [
            template_engines.create_engine(self.get_id(), engine_conf)
            for engine_conf in config.get("template_engines", [])
        ]

    def refresh_or_fetch(self) -> None:
        if mode.is_master():
            self.refresh()
        else:
            self.fetch()

    def refresh(self) -> None:
        _LOG.info("Doing a refresh of %s", self.get_id())
        try:
            self._is_loaded = False
            with _REFRESH_SUMMARY.labels(self.get_id()).time():
                self._do_refresh()
            self._eval_templates()
            _set_refresh_success(source=self.get_id())
        except Exception:
            _LOG.exception("Error with source %s", self.get_id())
            _REFRESH_ERROR_COUNTER.labels(self.get_id()).inc()
            _REFRESH_ERROR_GAUGE.labels(self.get_id()).set(1)
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
            with _TEMPLATE_SUMMARY.labels(self.get_id(), engine.get_type()).time():
                engine.evaluate(root_dir, files)

    def fetch(self) -> None:
        try:
            self._is_loaded = False
            with (
                _FETCH_SUMMARY.labels(self.get_id()).time(),
                _FETCH_ERROR_COUNTER.labels(self.get_id()).count_exceptions(),
            ):
                self._do_fetch()
            self._eval_templates()
            _set_fetch_success(source=self.get_id())
        except Exception:
            _LOG.exception("Error with source %s", self.get_id())
            _FETCH_ERROR_GAUGE.labels(self.get_id()).set(1)
            raise
        finally:
            self._is_loaded = True

    def _do_refresh(self) -> None:
        pass

    def _do_fetch(self) -> None:
        path = self.get_path()
        url = mode.get_fetch_url(self.get_id())

        for i in list(range(_RETRY_NUMBER))[::-1]:
            try:
                _LOG.info("Doing a fetch of %s", self.get_id())
                response = requests.get(url, headers={"X-Scm-Secret": os.environ["SCM_SECRET"]}, stream=True)
                response.raise_for_status()
                if os.path.exists(path):
                    shutil.rmtree(path)
                os.makedirs(path, exist_ok=True)
                with subprocess.Popen(  # nosec
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
            except Exception as exception:  # pylint: disable=broad-exception-caught
                _DO_FETCH_ERROR_COUNTER.labels(self.get_id()).inc()
                retry_message = f" (will retry in {_RETRY_DELAY}s)" if i else " (failed)"
                _LOG.warning(
                    "Error fetching the source %s from the master%s: %s",
                    self.get_id(),
                    retry_message,
                    str(exception),
                )
                if i:
                    time.sleep(_RETRY_DELAY)
                else:
                    raise

    def _copy(self, source: str, excludes: Optional[list[str]] = None) -> None:
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
        with _COPY_SUMMARY.labels(self.get_id()).time():
            self._exec(*cmd)

    def delete_target_dir(self) -> None:
        dest = self.get_path()
        _LOG.info("Deleting target dir %s", dest)
        if os.path.isdir(dest):
            shutil.rmtree(dest)

    def get_path(self) -> str:
        if "target_dir" in self._config:
            target_dir = self._config["target_dir"]
            if target_dir.startswith("/"):
                return target_dir
            else:
                return _MASTER_TARGET if self._is_master else os.path.join(_TARGET, target_dir)
        else:
            return _MASTER_TARGET if self._is_master else os.path.join(_TARGET, self.get_id())

    def get_id(self) -> str:
        return self._id

    def validate_auth(self, request: pyramid.request.Request) -> None:
        permission = request.has_permission("all", self.get_config())
        if not isinstance(permission, Allowed):
            raise HTTPForbidden("Not allowed to access this source")

    def is_master(self) -> bool:
        return self._is_master

    def get_stats(self) -> SourceStatus:
        config_copy = copy.deepcopy(self._config)
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
            _LOG.debug("Running: %s", " ".join(args_))
            output: str = (
                subprocess.run(  # nosec
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
                _LOG.debug(output)
            return output
        except subprocess.CalledProcessError as exception:
            _LOG.error(exception.output.decode("utf-8").strip())
            raise

    def is_loaded(self) -> bool:
        return self._is_loaded

    @staticmethod
    def _hide_sensitive(data: Optional[dict[str, str]]) -> None:
        if data is None:
            return
        for key in list(data.keys()):
            k = key.upper()
            if "KEY" in k or "PASSWORD" in k or "SECRET" in k:
                data[key] = "•••"


@broadcast.decorator(expect_answers=False)
def _set_refresh_success(source: str) -> None:
    """Set refresh in success in all process."""

    _REFRESH_ERROR_GAUGE.labels(source=source).set(0)


@broadcast.decorator(expect_answers=False)
def _set_fetch_success(source: str) -> None:
    """Set fetch in success in all process."""

    _FETCH_ERROR_GAUGE.labels(source=source).set(0)
