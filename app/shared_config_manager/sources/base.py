import asyncio
import copy
import logging
import os
import shutil
import subprocess  # nosec
from pathlib import Path
from typing import Any, Protocol, cast

import aiohttp
from c2casgiutils import broadcast
from fastapi import HTTPException, Request
from prometheus_client import Counter, Gauge, Summary

from shared_config_manager import broadcast_status, config, template_engines
from shared_config_manager.configuration import SourceConfig
from shared_config_manager.security import Allowed, User, permits
from shared_config_manager.sources import mode

_LOG = logging.getLogger(__name__)

_REFRESH_SUMMARY = Summary("sharedconfigmanager_source_refresh", "Number of source refreshes", ["source"])
_REFRESH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_refresh_error_counter",
    "Number of source errors",
    ["source"],
)
_REFRESH_ERROR_GAUGE = Gauge(
    "sharedconfigmanager_source_refresh_error_status",
    "Sources in error",
    ["source"],
)
_TEMPLATE_SUMMARY = Summary(
    "sharedconfigmanager_source_template",
    "Number of template evaluations",
    ["source", "type"],
)
_FETCH_SUMMARY = Summary("sharedconfigmanager_source_fetch", "Number of source fetches", ["source"])
_FETCH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_fetch_error_counter",
    "Number of source errors",
    ["source"],
)
_FETCH_ERROR_GAUGE = Gauge("sharedconfigmanager_source_fetch_error_status", "Sources in error", ["source"])
_DO_FETCH_ERROR_COUNTER = Counter(
    "sharedconfigmanager_source_do_fetch_error",
    "Number of source fetch errors",
    ["source"],
)
_COPY_SUMMARY = Summary("sharedconfigmanager_source_copy", "Number of source copies", ["source"])


class BaseSource:
    """Base class for sources."""

    def __init__(self, id_: str, config: SourceConfig, is_master: bool) -> None:
        self._id = id_
        self._config = config
        self._is_master = is_master
        self._is_loaded = False
        self._template_engines = [
            template_engines.create_engine(self.get_id(), engine_conf)
            for engine_conf in config.get("template_engines", [])
        ]

    async def refresh_or_fetch(self) -> None:
        if mode.is_master():
            await self.refresh()
        else:
            await self.fetch()

    async def refresh(self) -> None:
        _LOG.info("Doing a refresh of %s", self.get_id())
        try:
            self._is_loaded = False
            with _REFRESH_SUMMARY.labels(self.get_id()).time():
                self._do_refresh()
            await self._eval_templates()
            await _set_refresh_success(source=self.get_id())
        except Exception:
            _LOG.warning("Error with source %s", self.get_id(), exc_info=True)
            _REFRESH_ERROR_COUNTER.labels(self.get_id()).inc()
            _REFRESH_ERROR_GAUGE.labels(self.get_id()).set(1)
            raise
        finally:
            self._is_loaded = True

    async def _eval_templates(self) -> None:
        if mode.is_master_with_slaves():
            # masters with slaves don't need to evaluate templates
            return
        # We get the list of files only once to avoid consecutive template engines eating the output of
        # the previous template engines. This method is always called with a root_dir that is clean from
        # all the files that are created by template engines (see the --delete rsync flag in
        # BaseSource._copy).
        root_dir = self.get_path()
        files = [p.relative_to(root_dir) for p in root_dir.glob("**/*")]

        for engine in self._template_engines:
            with _TEMPLATE_SUMMARY.labels(self.get_id(), engine.get_type()).time():
                engine.evaluate(root_dir, files)

    async def fetch(self) -> None:
        try:
            self._is_loaded = False
            with (
                _FETCH_SUMMARY.labels(self.get_id()).time(),
                _FETCH_ERROR_COUNTER.labels(self.get_id()).count_exceptions(),
            ):
                await self._do_fetch()
            await self._eval_templates()
            await _set_fetch_success(source=self.get_id())
        except Exception:
            _LOG.warning("Error with source %s", self.get_id(), exc_info=True)
            _FETCH_ERROR_GAUGE.labels(self.get_id()).set(1)
            raise
        finally:
            self._is_loaded = True

    def _do_refresh(self) -> None:
        pass

    async def _do_fetch(self) -> None:
        path = self.get_path()
        url = mode.get_fetch_url(self.get_id())

        for i in list(range(config.settings.retry_number))[::-1]:
            try:
                _LOG.info("Doing a fetch of %s, on %s", self.get_id(), url)
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        url,
                        headers={"X-Scm-Secret": config.settings.secret or ""},
                        timeout=config.settings.requests_timeout,
                    ) as response,
                ):
                    response.raise_for_status()
                    if path.exists():
                        shutil.rmtree(path)
                    path.mkdir(parents=True, exist_ok=True)
                    tar = await asyncio.create_subprocess_exec(
                        "tar",
                        "--extract",
                        "--gzip",
                        "--no-same-owner",
                        "--no-same-permissions",
                        "--touch",
                        "--no-overwrite-dir",
                        cwd=path,
                        stdin=asyncio.subprocess.PIPE,
                    )
                    if tar.stdin is not None:
                        async for chunk in response.content.iter_chunked(8192):
                            tar.stdin.write(chunk)
                        tar.stdin.close()
                    await tar.wait()
            except Exception as exception:  # pylint: disable=broad-exception-caught
                if not isinstance(exception, aiohttp.ClientConnectorError):
                    _LOG.exception("Unexpected error while fetching the source from url %s", url)
                _DO_FETCH_ERROR_COUNTER.labels(self.get_id()).inc()
                retry_message = f" (will retry in {config.settings.retry_delay}s)" if i else " (failed)"
                _LOG.warning(
                    "Error fetching the source %s from the master%s: %s",
                    self.get_id(),
                    retry_message,
                    str(exception),
                )
                if i:
                    await asyncio.sleep(config.settings.retry_delay)
                else:
                    raise
            else:
                return

    def _copy(self, source: Path, excludes: list[str] | None = None) -> None:
        self.get_path().mkdir(parents=True, exist_ok=True)
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
        cmd += [str(source) + "/", str(self.get_path())]
        with _COPY_SUMMARY.labels(self.get_id()).time():
            self._exec(*cmd)

    def delete_target_dir(self) -> None:
        dest = self.get_path()
        _LOG.info("Deleting target dir %s", dest)
        if dest.is_dir():
            shutil.rmtree(dest)

    def get_path(self) -> Path:
        if "target_dir" in self._config:
            target_dir = self._config["target_dir"]
            if target_dir.startswith("/"):
                return Path(target_dir)
            return config.settings.master_target if self._is_master else config.settings.target / target_dir
        return config.settings.master_target if self._is_master else config.settings.target / self.get_id()

    def get_id(self) -> str:
        return self._id

    async def validate_auth(self, identity: User | None, request: Request) -> None:
        permission = await permits(identity, self.get_config(), self._id)
        if not isinstance(permission, Allowed):
            if identity is not None:
                message = "Not allowed to access this source"
                raise HTTPException(status_code=403, detail=message)

            # To avoid circular import
            from shared_config_manager import (  # noqa: PLC0415 # pylint: disable=cyclic-import
                main,
            )

            raise HTTPException(
                status_code=302,
                headers={
                    "location": main.app.url_path_for("c2c_github_login") + "?came_from=" + request.url.path,
                },
            )

    def is_master(self) -> bool:
        return self._is_master

    def get_stats(self) -> broadcast_status.SourceStatus:
        config_copy = copy.deepcopy(self._config)
        stats_ = cast("broadcast_status.SourceStatus", config_copy)
        for template_stats, template_engine in zip(
            stats_.get("template_engines", []),
            self._template_engines,
            strict=False,
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
                subprocess.run(  # noqa: S603
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
        except subprocess.CalledProcessError as exception:
            _LOG.warning(exception.output.decode("utf-8").strip())
            raise
        else:
            return output

    def is_loaded(self) -> bool:
        return self._is_loaded

    @staticmethod
    def _hide_sensitive(data: dict[str, str] | None) -> None:
        if data is None:
            return
        for key in list(data.keys()):
            k = key.upper()
            if "KEY" in k or "PASSWORD" in k or "SECRET" in k:
                data[key] = "•••"


class _SetRefreshSuccessProto(Protocol):
    """Protocol for _set_refresh_success function."""

    async def __call__(self, *, source: str) -> list[None] | None: ...


_set_refresh_success: _SetRefreshSuccessProto = None  # type: ignore[assignment]


async def __set_refresh_success(source: str) -> None:
    """Set refresh in success in all process."""
    _REFRESH_ERROR_GAUGE.labels(source=source).set(0)


class _SetFetchSuccessProto(Protocol):
    """Protocol for _set_fetch_success function."""

    async def __call__(self, *, source: str) -> list[None] | None: ...


_set_fetch_success: _SetFetchSuccessProto = None  # type: ignore[assignment]


async def __set_fetch_success(source: str) -> None:
    """Set fetch in success in all process."""
    _FETCH_ERROR_GAUGE.labels(source=source).set(0)


async def init() -> None:
    """Initialize the base source manager."""

    global _set_refresh_success, _set_fetch_success  # noqa: PLW0603
    _set_refresh_success = await broadcast.decorate(__set_refresh_success, expect_answers=False)
    _set_fetch_success = await broadcast.decorate(__set_fetch_success, expect_answers=False)
