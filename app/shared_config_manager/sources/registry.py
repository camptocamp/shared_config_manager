import logging
import os
import subprocess  # nosec
import tempfile
from collections.abc import Mapping
from pathlib import Path
from threading import Thread

import inotify.adapters
import pyramid.request
import yaml
from c2cwsgiutils import broadcast
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound

from shared_config_manager.configuration import Config, SourceConfig, SourceStatus
from shared_config_manager.sources import base, git, mode, rclone, rsync

_LOG = logging.getLogger(__name__)
_ENGINES = {"git": git.GitSource, "rsync": rsync.RsyncSource, "rclone": rclone.RcloneSource}
_MASTER_ID = "master"
MASTER_SOURCE: base.BaseSource | None = None
_SOURCES: dict[str, base.BaseSource] = {}
FILTERED_SOURCES: Mapping[str, base.BaseSource] = {}
_TAG_FILTER = os.environ.get("TAG_FILTER")


def _create_source(id_: str, config: SourceConfig, is_master: bool = False) -> base.BaseSource:
    type_ = config["type"]
    return _ENGINES[type_](id_, config, is_master)


def get_sources() -> Mapping[str, base.BaseSource]:
    """Get all the sources."""
    copy = dict(_SOURCES.items())
    copy.update(FILTERED_SOURCES)
    return copy


def init(slave: bool) -> None:
    """Initialize the registry."""
    global MASTER_SOURCE  # pylint: disable=global-statement
    mode.init(slave)
    if slave:
        broadcast.subscribe("slave_fetch", _slave_fetch)
    _update_flag("LOADING")
    _prepare_ssh()
    if os.environ.get("MASTER_CONFIG"):
        _LOG.info("Load the master config from environment variable")
        content = yaml.load(os.environ["MASTER_CONFIG"], Loader=yaml.SafeLoader)
    else:
        _LOG.info("Load the master config from config file")
        with Path("/etc/shared_config_manager/config.yaml").open(encoding="utf-8") as scm_file:
            content = yaml.load(scm_file, Loader=yaml.SafeLoader)

        def thread() -> None:
            inotify_ = inotify.adapters.Inotify()
            inotify_.add_watch("/etc/shared_config_manager/config.yaml")
            for _, type_names, path, filename in inotify_.event_gen(yield_nones=False):
                _LOG.debug("Inotify event: %s / %s: [%s]", path, filename, ",".join(type_names))
                if (
                    "IN_CLOSE_WRITE" in type_names or "IN_IGNORED" in type_names
                ):  # the IN_IGNORED it for move file on this one
                    _LOG.info("Reload the master config from config file")
                    with Path("/etc/shared_config_manager/config.yaml").open(encoding="utf-8") as scm_file:
                        config = yaml.load(scm_file, Loader=yaml.SafeLoader)
                    _handle_master_config(config)

        thread_instance = Thread(target=thread, daemon=True)
        thread_instance.start()

    if content.get("sources", False) is not False:
        _LOG.info("The master config is inline")
        content["standalone"] = True
        # A fake master source to have auth work
        MASTER_SOURCE = base.BaseSource(_MASTER_ID, content, is_master=True)
        Thread(target=_handle_master_config, args=[content], name="master_config_loader", daemon=True).start()
    else:
        MASTER_SOURCE = _create_source(_MASTER_ID, content, is_master=True)
        _LOG.info("Initial loading of the master config")
        MASTER_SOURCE.refresh_or_fetch()
        _LOG.info("Loading of the master config finished")
        if not MASTER_SOURCE.get_config().get("standalone", False):
            Thread(target=reload_master_config, name="master_config_loader", daemon=True).start()


def reload_master_config() -> None:
    """Reload the master config."""
    if MASTER_SOURCE:
        with (MASTER_SOURCE.get_path() / "shared_config_manager.yaml").open(
            encoding="utf-8",
        ) as config_file:
            config = yaml.load(config_file, Loader=yaml.SafeLoader)
            _handle_master_config(config)


def _do_handle_master_config(config: Config) -> tuple[int, int]:
    global FILTERED_SOURCES  # pylint: disable=global-statement

    success = 0
    errors = 0

    new_sources, filtered = _filter_sources(config["sources"])
    FILTERED_SOURCES = {id_: _create_source(id_, config) for id_, config in filtered.items()}

    to_deletes = set(_SOURCES.keys()) - set(new_sources.keys())
    for to_delete in to_deletes:
        _delete_source(to_delete)
    for id_, source_config in new_sources.items():
        prev_source = _SOURCES.get(id_)
        if prev_source is None:
            _LOG.info("New source detected: %s", id_)
        elif prev_source.get_config() == source_config:
            _LOG.debug("Source %s didn't change, not reloading it", id_)
            continue
        else:
            _LOG.info("Change detected in source %s, reloading it", id_)
            _delete_source(id_)  # to be sure the old stuff is cleaned

        try:
            _SOURCES[id_] = _create_source(id_, source_config)
            _SOURCES[id_].refresh_or_fetch()
            success += 1
        except Exception:  # pylint: disable=broad-exception-caught
            _LOG.error("Cannot load the %s config", id_, exc_info=True)
            errors += 1
    return success, errors


def _handle_master_config(config: Config) -> None:
    _LOG.info("Reading the master config")
    if _MASTER_ID in config["sources"]:
        message = f"A source cannot have the {_MASTER_ID} id"
        raise HTTPBadRequest(message)
    success, errors = _do_handle_master_config(config)
    if errors != 0:
        if success != 0:
            success, errors = _do_handle_master_config(config)
            _update_flag("READY")
        else:
            _update_flag("ERROR")
    else:
        _update_flag("READY")


def _update_flag(value: str) -> None:
    with (Path(tempfile.gettempdir()) / "status").open("w", encoding="utf-8") as flag:
        flag.write(value)


def _prepare_ssh() -> None:
    home = Path.home()
    other_ssh = home.joinpath(".ssh2")
    if other_ssh.is_dir():
        ssh = home.joinpath(".ssh")
        subprocess.check_call(  # noqa: S603 # nosec
            [  # noqa: S607
                "rsync",
                "--recursive",
                "--copy-links",
                "--chmod=D0700,F0600",
                str(other_ssh) + "/",
                str(ssh) + "/",
            ],
        )


def _delete_source(id_: str) -> None:
    _SOURCES[id_].delete()
    del _SOURCES[id_]


def _filter_sources(
    source_configs: dict[str, SourceConfig],
) -> tuple[dict[str, SourceConfig], dict[str, SourceConfig]]:
    if _TAG_FILTER is None or mode.is_master():
        return source_configs, {}
    result = {}
    filtered = {}
    for id_, config in source_configs.items():
        if _TAG_FILTER in config.get("tags", []):
            result[id_] = config
        else:
            filtered[id_] = config
    return result, filtered


def refresh(id_: str, request: pyramid.request.Request | None) -> None:
    """
    Do a refresh.

    This is called from the web service to start a refresh.
    """
    _LOG.info("Reloading the %s config", id_)
    source, _ = get_source_check_auth(id_, request)
    if source is None:
        message = f"Unknown id {id_}"
        raise HTTPNotFound(message)
    source.refresh()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        reload_master_config()
    broadcast.broadcast("slave_fetch", params={"id_": id_})


def _slave_fetch(id_: str) -> None:
    """Do a refresh on the slave."""
    source, filtered = get_source_check_auth(id_, None)
    if source is None:
        _LOG.error("Unknown id %d", id_)
        return
    if filtered and not mode.is_master():
        _LOG.info("The reloading the %s config is filtered", id_)
        return
    _LOG.info("Reloading the %s config from event", id_)
    if not source.is_master() or os.environ.get("SCM_MASTER_DISPATCH", "TRUE").lower() in ["true", "1", "on"]:
        source.fetch()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        reload_master_config()


def get_source_check_auth(
    id_: str,
    request: pyramid.request.Request | None,
) -> tuple[base.BaseSource | None, bool]:
    """Get a source by id and check the auth."""
    filtered = False
    source = get_source(id_)
    if source is None:
        source = FILTERED_SOURCES.get(id_)
        filtered = True
    if source is not None:
        if request is not None:
            source.validate_auth(request)
        return source, filtered
    return None, filtered


def get_source(id_: str) -> base.BaseSource | None:
    """Get a source by id."""
    if MASTER_SOURCE and MASTER_SOURCE.get_id() == id_:
        return MASTER_SOURCE
    return _SOURCES.get(id_)


def get_stats() -> dict[str, SourceStatus]:
    """Get the stats of all the sources."""
    return (
        {
            id_: source.get_stats()
            for id_, source in {**_SOURCES, MASTER_SOURCE.get_id(): MASTER_SOURCE}.items()
        }
        if MASTER_SOURCE
        else {}
    )
