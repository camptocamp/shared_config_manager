import asyncio
import logging
import tempfile
from collections.abc import Mapping
from pathlib import Path

import aiofiles
import yaml
from asyncinotify import Inotify, Mask
from c2casgiutils import broadcast
from fastapi import HTTPException, Request

from shared_config_manager import config
from shared_config_manager.configuration import Config, SourceConfig, SourceStatus
from shared_config_manager.security import User
from shared_config_manager.sources import base, git, mode, rclone, rsync

_LOG = logging.getLogger(__name__)
_ENGINES = {"git": git.GitSource, "rsync": rsync.RsyncSource, "rclone": rclone.RcloneSource}
_MASTER_ID = "master"
MASTER_SOURCE: base.BaseSource | None = None
_SOURCES: dict[str, base.BaseSource] = {}
FILTERED_SOURCES: Mapping[str, base.BaseSource] = {}


def _create_source(source_id: str, config: SourceConfig, is_master: bool = False) -> base.BaseSource:
    type_ = config["type"]
    return _ENGINES[type_](source_id, config, is_master)


def get_sources() -> Mapping[str, base.BaseSource]:
    """Get all the sources."""
    copy = dict(_SOURCES.items())
    copy.update(FILTERED_SOURCES)
    return copy


_WATCH_CONFIG_TASK: asyncio.Task[None] | None = None


async def init(slave: bool) -> None:
    """Initialize the registry."""
    global MASTER_SOURCE  # noqa: PLW0603
    mode.init(slave)
    if slave:
        await broadcast.subscribe("slave_fetch", _slave_fetch)
    await update_flag("LOADING")
    await _prepare_ssh()
    if config.settings.master_config:
        _LOG.info("Load the master config from environment variable")
        content = yaml.load(config.settings.master_config, Loader=yaml.SafeLoader)
    else:
        _LOG.info("Load the master config from config file")
        async with aiofiles.open("/etc/shared_config_manager/config.yaml", encoding="utf-8") as scm_file:
            content = yaml.load(await scm_file.read(), Loader=yaml.SafeLoader)

        async def watch_config() -> None:
            with Inotify() as inotify:
                main_config_path = Path("/etc/shared_config_manager/config.yaml")
                # Watch for modifications and deletions (move) of the config file
                inotify.add_watch(main_config_path, Mask.CLOSE_WRITE | Mask.IGNORED)
                async for _ in inotify:
                    _LOG.info("Reload the master config from config file")
                    async with aiofiles.open(main_config_path, encoding="utf-8") as scm_file:
                        config = yaml.load(await scm_file.read(), Loader=yaml.SafeLoader)
                    await _handle_master_config(config)

        global _WATCH_CONFIG_TASK  # noqa: PLW0603
        _WATCH_CONFIG_TASK = asyncio.create_task(watch_config())

    if content.get("sources", False) is not False:
        _LOG.info("The master config is inline")
        content["standalone"] = True
        # A fake master source to have auth work
        MASTER_SOURCE = base.BaseSource(_MASTER_ID, content, is_master=True)
        await _handle_master_config(content)
    else:
        MASTER_SOURCE = _create_source(_MASTER_ID, content, is_master=True)
        _LOG.info("Initial loading of the master config")
        await MASTER_SOURCE.refresh_or_fetch()
        _LOG.info("Loading of the master config finished")
        if not MASTER_SOURCE.get_config().get("standalone", False):
            await reload_master_config()


async def reload_master_config() -> None:
    """Reload the master config."""
    if MASTER_SOURCE:
        async with aiofiles.open(
            MASTER_SOURCE.get_path() / "shared_config_manager.yaml",
            encoding="utf-8",
        ) as config_file:
            config = yaml.load(await config_file.read(), Loader=yaml.SafeLoader)
            await _handle_master_config(config)


async def _do_handle_master_config(config: Config) -> tuple[int, int]:
    global FILTERED_SOURCES  # noqa: PLW0603

    success = 0
    errors = 0

    new_sources, filtered = _filter_sources(config["sources"])
    FILTERED_SOURCES = {
        source_id: _create_source(source_id, config) for source_id, config in filtered.items()
    }

    to_deletes = set(_SOURCES.keys()) - set(new_sources.keys())
    for to_delete in to_deletes:
        _delete_source(to_delete)
    for source_id, source_config in new_sources.items():
        prev_source = _SOURCES.get(source_id)
        if prev_source is None:
            _LOG.info("New source detected: %s", source_id)
        elif prev_source.get_config() == source_config:
            _LOG.debug("Source %s didn't change, not reloading it", source_id)
            continue
        else:
            _LOG.info("Change detected in source %s, reloading it", source_id)
            _delete_source(source_id)  # to be sure the old stuff is cleaned

        try:
            _SOURCES[source_id] = _create_source(source_id, source_config)
            await _SOURCES[source_id].refresh_or_fetch()
            success += 1
        except Exception:  # noqa: BLE001
            _LOG.error("Cannot load the %s config", source_id, exc_info=True)
            errors += 1
    return success, errors


async def _handle_master_config(config: Config) -> None:
    _LOG.info("Reading the master config")
    if _MASTER_ID in config["sources"]:
        message = f"A source cannot have the {_MASTER_ID} id"
        raise HTTPException(status_code=400, detail=message)
    success, errors = await _do_handle_master_config(config)
    if errors != 0:
        if success != 0:
            success, errors = await _do_handle_master_config(config)
            await update_flag("READY")
        else:
            await update_flag("ERROR")
    else:
        await update_flag("READY")


async def update_flag(value: str) -> None:
    """Update the status flag."""
    async with aiofiles.open(Path(tempfile.gettempdir()) / "status", "w", encoding="utf-8") as flag:
        await flag.write(value)


async def _prepare_ssh() -> None:
    home = Path.home()
    other_ssh = home.joinpath(".ssh2")
    if other_ssh.is_dir():
        ssh = home.joinpath(".ssh")
        proc = await asyncio.create_subprocess_exec(
            "rsync",
            "--recursive",
            "--copy-links",
            "--chmod=D0700,F0600",
            str(other_ssh) + "/",
            str(ssh) + "/",
        )
        await proc.wait()


def _delete_source(source_id: str) -> None:
    _SOURCES[source_id].delete()
    del _SOURCES[source_id]


def _filter_sources(
    source_configs: dict[str, SourceConfig],
) -> tuple[dict[str, SourceConfig], dict[str, SourceConfig]]:
    if config.settings.tag_filter is None or mode.is_master():
        return source_configs, {}
    result = {}
    filtered = {}
    for source_id, source_config in source_configs.items():
        if config.settings.tag_filter in source_config.get("tags", []):
            result[source_id] = source_config
        else:
            filtered[source_id] = source_config
    return result, filtered


async def refresh(source_id: str, identity: User | None, request: Request) -> None:
    """
    Do a refresh.

    This is called from the web service to start a refresh.
    """
    source, _ = await get_source_check_auth(source_id, identity, request=request)
    _LOG.info("Reloading the %s config", source_id)
    if source is None:
        message = f"Unknown id {source_id}"
        raise HTTPException(status_code=404, detail=message)
    await source.refresh()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        await reload_master_config()
    await broadcast.broadcast("slave_fetch", params={"source_id": source_id})


async def _slave_fetch(source_id: str) -> None:
    """Do a refresh on the slave."""
    source, filtered = await get_source_check_auth(source_id, None, check_auth=False)
    if source is None:
        _LOG.error("Unknown id %s", source_id)
        return
    if filtered and not mode.is_master():
        _LOG.info("The reloading the %s config is filtered", source_id)
        return
    _LOG.info("Reloading the %s config from event", source_id)
    if not source.is_master() or config.settings.master_dispatch:
        await source.fetch()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        await reload_master_config()


async def get_source_check_auth(
    source_id: str,
    identity: User | None,
    request: Request | None = None,
    check_auth: bool = True,
) -> tuple[base.BaseSource | None, bool]:
    """Get a source by id and check the auth."""
    filtered = False
    source = get_source(source_id)
    if source is None:
        source = FILTERED_SOURCES.get(source_id)
        filtered = True
    if source is not None:
        if check_auth:
            assert request is not None
            await source.validate_auth(identity, request)
        return source, filtered
    return None, filtered


def get_source(source_id: str) -> base.BaseSource | None:
    """Get a source by id."""
    if MASTER_SOURCE and MASTER_SOURCE.get_id() == source_id:
        return MASTER_SOURCE
    return _SOURCES.get(source_id)


def get_stats() -> dict[str, SourceStatus]:
    """Get the stats of all the sources."""
    return (
        {
            source_id: source.get_stats()
            for source_id, source in {**_SOURCES, MASTER_SOURCE.get_id(): MASTER_SOURCE}.items()
        }
        if MASTER_SOURCE
        else {}
    )
