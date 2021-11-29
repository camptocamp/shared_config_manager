import logging
import os
import pathlib
import subprocess
import tempfile
from threading import Thread
from typing import Any, Dict, Mapping, Optional, Tuple

import inotify.adapters
import yaml
from c2cwsgiutils import broadcast
from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden, HTTPNotFound

from shared_config_manager.sources import base, file, git, mode, rclone, rsync

ENGINES = {
    "git": git.GitSource,
    "rsync": rsync.RsyncSource,
    "rclone": rclone.RcloneSource,
    "file": file.FileSource,
}
LOG = logging.getLogger(__name__)
MASTER_ID = "master"
MASTER_SOURCE: Optional[base.BaseSource] = None
SOURCES: Dict[str, base.BaseSource] = {}
FILTERED_SOURCES: Mapping[str, base.BaseSource] = {}
TAG_FILTER = os.environ.get("TAG_FILTER")


def _create_source(id_, config, is_master=False, default_key=None) -> base.BaseSource:
    type_ = config["type"]
    return ENGINES[type_](id_, config, is_master, default_key)


def get_sources() -> Mapping[str, base.BaseSource]:
    copy = dict(SOURCES.items())
    copy.update(FILTERED_SOURCES)
    return copy


def init(slave: bool) -> None:
    global MASTER_SOURCE  # pylint: disable=global-statement
    mode.init(slave)
    if slave:
        broadcast.subscribe("slave_fetch", _slave_fetch)
    _update_flag("LOADING")
    _prepare_ssh()
    if os.environ.get("MASTER_CONFIG"):
        LOG.info("Load the master config from environment variable")
        content = yaml.load(os.environ["MASTER_CONFIG"], Loader=yaml.SafeLoader)
    else:
        LOG.info("Load the master config from config file")
        with open("/etc/shared_config_manager/config.yaml", encoding="utf-8") as scm_file:
            content = yaml.load(scm_file, Loader=yaml.SafeLoader)

        def thread() -> None:
            inotify_ = inotify.adapters.Inotify()
            inotify_.add_watch("/etc/shared_config_manager/config.yaml")
            for _, type_names, path, filename in inotify_.event_gen(yield_nones=False):
                LOG.debug("Inotify event: %s / %s: [%s]", path, filename, ",".join(type_names))
                if "IN_CLOSE_WRITE" in type_names:
                    LOG.info("Reload the master config from config file")
                    with open("/etc/shared_config_manager/config.yaml", encoding="utf-8") as scm_file:
                        config = yaml.load(scm_file, Loader=yaml.SafeLoader)
                    _handle_master_config(config)

        thread_instance = Thread(target=thread, daemon=True)
        thread_instance.start()

    if content.get("sources", False) is not False:
        LOG.info("The master config is inline")
        content["standalone"] = True
        # A fake master source to have auth work
        MASTER_SOURCE = base.BaseSource(MASTER_ID, content, is_master=True, default_key=content.get("key"))
        Thread(target=_handle_master_config, args=[content], name="master_config_loader", daemon=True).start()
    else:
        MASTER_SOURCE = _create_source(MASTER_ID, content, is_master=True)
        LOG.info("Initial loading of the master config")
        MASTER_SOURCE.refresh_or_fetch()
        LOG.info("Loading of the master config finished")
        if not MASTER_SOURCE.get_config().get("standalone", False):
            Thread(target=reload_master_config, name="master_config_loader", daemon=True).start()


def reload_master_config():
    if MASTER_SOURCE:
        with open(
            os.path.join(MASTER_SOURCE.get_path(), "shared_config_manager.yaml"), encoding="utf-8"
        ) as config_file:
            config = yaml.load(config_file, Loader=yaml.SafeLoader)
            _handle_master_config(config)


def _handle_master_config(config: Mapping[str, Any]) -> None:
    global FILTERED_SOURCES  # pylint: disable=global-statement
    LOG.info("Reading the master config")
    if MASTER_ID in config["sources"]:
        raise HTTPBadRequest(f'A source cannot have the "{MASTER_ID}" id')
    new_sources, filtered = _filter_sources(config["sources"])
    FILTERED_SOURCES = {id_: _create_source(id_, config) for id_, config in filtered.items()}
    to_deletes = set(SOURCES.keys()) - set(new_sources.keys())
    for to_delete in to_deletes:
        _delete_source(to_delete)
    errors = 0
    for id_, source_config in new_sources.items():
        prev_source = SOURCES.get(id_)
        if prev_source is None:
            LOG.info("New source detected: %s", id_)
        elif prev_source.get_config() == source_config:
            LOG.debug("Source %s didn't change, not reloading it", id_)
            continue
        else:
            LOG.info("Change detected in source %s, reloading it", id_)
            _delete_source(id_)  # to be sure the old stuff is cleaned

        try:
            SOURCES[id_] = _create_source(id_, source_config, default_key=config.get("key"))
            SOURCES[id_].refresh_or_fetch()
        except Exception:
            LOG.error("Cannot load the %s config", id_, exc_info=True)
            errors += 1
    _update_flag("READY" if errors == 0 else "ERROR")


def _update_flag(value):
    with open(os.path.join(tempfile.gettempdir(), "status"), "w", encoding="utf-8") as flag:
        flag.write(value)


def _prepare_ssh():
    home = pathlib.Path.home()
    other_ssh = home.joinpath(".ssh2")
    if other_ssh.is_dir():
        ssh = home.joinpath(".ssh")
        subprocess.check_call(
            [
                "rsync",
                "--recursive",
                "--copy-links",
                "--chmod=D0700,F0600",
                str(other_ssh) + "/",
                str(ssh) + "/",
            ]
        )


def _delete_source(id_):
    SOURCES[id_].delete()
    del SOURCES[id_]


def _filter_sources(source_configs):
    if TAG_FILTER is None or mode.is_master():
        return source_configs, {}
    result = {}
    filtered = {}
    for id_, config in source_configs.items():
        if TAG_FILTER in config.get("tags", []):
            result[id_] = config
        else:
            filtered[id_] = config
    return result, filtered


def refresh(id_, key):
    """
    This is called from the web service to start a refresh.
    """
    LOG.info("Reloading the %s config", id_)
    source, _ = check_id_key(id_, key)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    source.refresh()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        reload_master_config()
    broadcast.broadcast("slave_fetch", params=dict(id_=id_, key=key))


def _slave_fetch(id_, key):
    """
    This is run on every slave when a source needs a refresh.
    """
    source, filtered = check_id_key(id_, key)
    if source is None:
        LOG.error("Unknown id %d", id_)
        return
    if filtered and not mode.is_master():
        LOG.info("The reloading the %s config is filtred", id_)
        return
    LOG.info("Reloading the %s config from event", id_)
    source.fetch()
    if source.is_master() and (not MASTER_SOURCE or not MASTER_SOURCE.get_config().get("standalone", False)):
        reload_master_config()


def check_id_key(id_, key) -> Tuple[Optional[base.BaseSource], bool]:
    filtered = False
    source = get_source(id_)
    if source is None:
        source = FILTERED_SOURCES.get(id_)
        filtered = True
    if source is not None and MASTER_SOURCE:
        try:
            source.validate_key(key)
        except HTTPForbidden:
            MASTER_SOURCE.validate_key(key)
        return source, filtered
    return None, filtered


def get_source(id_) -> Optional[base.BaseSource]:
    if MASTER_SOURCE and MASTER_SOURCE.get_id() == id_:
        return MASTER_SOURCE
    else:
        return SOURCES.get(id_)


def get_stats():
    return (
        {
            id_: source.get_stats()
            for id_, source in {**SOURCES, MASTER_SOURCE.get_id(): MASTER_SOURCE}.items()
        }
        if MASTER_SOURCE
        else {}
    )
