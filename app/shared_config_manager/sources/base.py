# Copyright (c) 2026, Camptocamp SA
import asyncio
import copy
import logging
import os
import shutil
import subprocess
import urllib.parse
import uuid
from typing import Any, Protocol

import aiohttp
from aiohttp import ClientTimeout
from anyio import Path, to_thread
from c2casgiutils import broadcast
from fastapi import HTTPException, Request
from prometheus_client import Counter, Gauge, Summary

from shared_config_manager import broadcast_status, config, template_engines
from shared_config_manager.configuration import SourceConfig, TemplateEnginesStatus
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
        self._lock = asyncio.Lock()
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
        async with self._lock:
            try:
                self._is_loaded = False
                with _REFRESH_SUMMARY.labels(self.get_id()).time():
                    await self._do_refresh()
                await self._eval_templates()
                await _set_refresh_success(source=self.get_id())
            except Exception:
                _LOG.warning("Error with source %s", self.get_id(), exc_info=True)
                _REFRESH_ERROR_COUNTER.labels(self.get_id()).inc()
                _REFRESH_ERROR_GAUGE.labels(self.get_id()).set(1)
                raise
            finally:
                self._is_loaded = True

    async def _eval_templates(self, root_dir: Path | None = None) -> None:
        if mode.is_master_with_slaves():
            # masters with slaves don't need to evaluate templates
            return
        # We get the list of files only once to avoid consecutive template engines eating the output of
        # the previous template engines. This method is always called with a root_dir that is clean from
        # all the files that are created by template engines (see the --delete rsync flag in
        # BaseSource._copy).
        if root_dir is None:
            root_dir = self.get_path()
        files = [p.relative_to(root_dir) async for p in root_dir.glob("**/*")]

        for engine in self._template_engines:
            with _TEMPLATE_SUMMARY.labels(self.get_id(), engine.get_type()).time():
                await engine.evaluate(root_dir, files)

    async def fetch(self) -> None:
        async with self._lock:
            tmp_dir: Path | None = None
            try:
                self._is_loaded = False
                await _cleanup_leftovers(self.get_path())
                with (
                    _FETCH_SUMMARY.labels(self.get_id()).time(),
                    _FETCH_ERROR_COUNTER.labels(self.get_id()).count_exceptions(),
                ):
                    tmp_dir = await self._do_fetch()
                await self._eval_templates(root_dir=tmp_dir)
                await self._install(tmp_dir)
                tmp_dir = None
                await _set_fetch_success(source=self.get_id())
            except Exception:
                _LOG.warning("Error with source %s", self.get_id(), exc_info=True)
                _FETCH_ERROR_GAUGE.labels(self.get_id()).set(1)
                raise
            finally:
                if tmp_dir is not None:
                    await _rmtree(tmp_dir)
                self._is_loaded = True

    async def _do_refresh(self) -> None:
        pass

    async def _do_fetch(self) -> Path:
        """
        Download the source tarball from the master and extract it in a temporary directory.

        The target directory is left untouched, the caller is responsible to install the
        fetched content, that way, the target directory is never empty nor partially updated.
        """
        path = self.get_path()
        url = mode.get_fetch_url(self.get_id())

        for i in list(range(config.settings.slave.retry_number))[::-1]:
            tmp_dir = path.parent / f".{path.name}.fetch-{uuid.uuid4().hex}"
            try:
                _LOG.info("Doing a fetch of %s, on %s", self.get_id(), url)
                async with (
                    aiohttp.ClientSession() as session,
                    session.get(
                        url,
                        headers={"X-Scm-Secret": config.settings.secret or ""},
                        timeout=ClientTimeout(total=config.settings.slave.requests_timeout),
                    ) as response,
                ):
                    response.raise_for_status()
                    await tmp_dir.mkdir(parents=True)
                    tar = await asyncio.create_subprocess_exec(
                        "tar",
                        "--extract",
                        "--gzip",
                        "--no-same-owner",
                        "--no-same-permissions",
                        "--touch",
                        "--no-overwrite-dir",
                        cwd=tmp_dir,
                        stdin=asyncio.subprocess.PIPE,
                    )
                    if tar.stdin is not None:
                        async for chunk in response.content.iter_chunked(8192):
                            tar.stdin.write(chunk)
                        tar.stdin.close()
                    assert await tar.wait() == 0
            except Exception as exception:  # pylint: disable=broad-exception-caught
                await _rmtree(tmp_dir)
                if not isinstance(exception, aiohttp.ClientConnectorError):
                    _LOG.exception("Unexpected error while fetching the source from url %s", url)
                _DO_FETCH_ERROR_COUNTER.labels(self.get_id()).inc()
                retry_message = f" (will retry in {config.settings.slave.retry_delay}s)" if i else " (failed)"
                _LOG.warning(
                    "Error fetching the source %s from the master%s: %s",
                    self.get_id(),
                    retry_message,
                    str(exception),
                )
                if i:
                    await asyncio.sleep(config.settings.slave.retry_delay)
                else:
                    raise
            else:
                return tmp_dir
        msg = "Number of retries exhausted"
        raise AssertionError(msg)

    async def _install(self, new_dir: Path) -> None:
        """Atomically replace the target directory with the fetched one."""
        path = self.get_path()
        backup = path.parent / f".{path.name}.old-{uuid.uuid4().hex}"
        try:
            await path.rename(backup)
        except FileNotFoundError:
            await new_dir.rename(path)
        else:
            try:
                await new_dir.rename(path)
            except Exception:
                # Restore the previous version if the installation failed
                await backup.rename(path)
                raise
            await _rmtree(backup)

    async def _copy(self, source: Path, excludes: list[str] | None = None) -> None:
        await self.get_path().mkdir(parents=True, exist_ok=True)
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

    async def delete_target_dir(self) -> None:
        dest = self.get_path()
        _LOG.info("Deleting target dir %s", dest)
        await _cleanup_leftovers(dest)
        if await dest.is_dir():
            await _rmtree(dest)

    def get_path(self) -> Path:
        if "target_dir" in self._config:
            target_dir = self._config["target_dir"]
            if target_dir.startswith("/"):
                return Path(target_dir)
            return (
                config.settings.master_target
                if self._is_master
                else config.settings.slave.target / target_dir
            )
        return (
            config.settings.master_target if self._is_master else config.settings.slave.target / self.get_id()
        )

    def get_id(self) -> str:
        return self._id

    async def validate_auth(
        self,
        identity: User | None,
        request: Request,
        access_type: str = "read",
    ) -> None:
        permission = await permits(identity, self.get_config(), self._id, access_type=access_type)
        if not isinstance(permission, Allowed):
            if identity is not None:
                access_label = "write access" if access_type == "write" else "access"
                message = f"Not allowed to {access_label} this source"
                raise HTTPException(status_code=403, detail=message)

            # To avoid circular import
            from shared_config_manager import (  # noqa: PLC0415 # pylint: disable=cyclic-import
                main,
            )

            raise HTTPException(
                status_code=302,
                headers={
                    "location": main.app.url_path_for("c2c_github_login")
                    + "?came_from="
                    + urllib.parse.quote(request.url.path),
                },
            )

    def is_master(self) -> bool:
        return self._is_master

    async def get_stats(self) -> broadcast_status.SourceStatus:
        config_copy = copy.deepcopy(self._config)
        for template_stats_config, template_engine in zip(
            config_copy.get("template_engines", []),
            self._template_engines,
            strict=False,
        ):
            template_stats = TemplateEnginesStatus.model_validate(
                {k: v for k, v in template_stats_config.items() if k != "environment_variables"}
            )
            template_engine.get_stats(template_stats)

            BaseSource._hide_sensitive(template_stats.data)
            BaseSource._hide_sensitive(template_stats.environment_variables)
            template_stats_config.update(template_stats.model_dump(exclude_none=True))  # type: ignore[typeddict-item]
        return broadcast_status.SourceStatus.model_validate(config_copy)

    def get_config(self) -> SourceConfig:
        return self._config

    def get_type(self) -> str:
        return self._config["type"]

    async def delete(self) -> None:
        await self.delete_target_dir()

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


async def _rmtree(path: Path) -> None:
    try:
        await to_thread.run_sync(shutil.rmtree, str(path))
    except FileNotFoundError:
        # Already removed by an other task or process
        pass


async def _cleanup_leftovers(path: Path) -> None:
    """Remove the temporary directories left by interrupted fetches of the source."""
    if not await path.parent.is_dir():
        return
    for pattern in (f".{path.name}.fetch-*", f".{path.name}.old-*"):
        async for leftover in path.parent.glob(pattern):
            if await leftover.is_dir():
                await _rmtree(leftover)


class _SetRefreshSuccessProto(Protocol):
    """Protocol for _set_refresh_success function."""

    async def __call__(self, *, source: str) -> None: ...


_set_refresh_success: _SetRefreshSuccessProto = None  # type: ignore[assignment]


def __set_refresh_success(source: str) -> None:
    """Set refresh in success in all process."""
    _REFRESH_ERROR_GAUGE.labels(source=source).set(0)


class _SetFetchSuccessProto(Protocol):
    """Protocol for _set_fetch_success function."""

    async def __call__(self, *, source: str) -> None: ...


_set_fetch_success: _SetFetchSuccessProto = None  # type: ignore[assignment]


def __set_fetch_success(source: str) -> None:
    """Set fetch in success in all process."""
    _FETCH_ERROR_GAUGE.labels(source=source).set(0)


async def init() -> None:
    """Initialize the base source manager."""

    global _set_refresh_success, _set_fetch_success  # noqa: PLW0603
    _set_refresh_success = await broadcast.decorate(__set_refresh_success, expect_answers=False)
    _set_fetch_success = await broadcast.decorate(__set_fetch_success, expect_answers=False)
