from c2cwsgiutils import broadcast
import logging
import os
import pathlib
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest, HTTPForbidden
import subprocess
import tempfile
from threading import Thread
from typing import Mapping, Any
import yaml

from . import git, rsync, base, rclone

ENGINES = {
    'git': git.GitSource,
    'rsync': rsync.RsyncSource,
    'rclone': rclone.RcloneSource
}
LOG = logging.getLogger(__name__)
MASTER_ID = 'master'
master_source: base.BaseSource = None
sources: Mapping[str, base.BaseSource] = {}
filtered_sources: Mapping[str, base.BaseSource] = {}
TAG_FILTER = os.environ.get("TAG_FILTER")


def _create_source(id_, config, is_master=False):
    type_ = config['type']
    return ENGINES[type_](id_, config, is_master)


def get_sources() -> Mapping[str, base.BaseSource]:
    global sources, filtered_sources
    copy = dict(sources.items())
    copy.update(filtered_sources)
    return copy


def init():
    global master_source
    _update_flag("LOADING")
    _prepare_ssh()
    content = yaml.load(os.environ['MASTER_CONFIG'])
    if content.get('sources', False):
        LOG.info("The master config is inline")
        # A fake master source to have auth work
        master_source = base.BaseSource(MASTER_ID, content, is_master=True)
        Thread(target=_handle_master_config(content), args=[content],
               name='master_config_loader', daemon=True).start()
    else:
        master_source = _create_source(MASTER_ID, content, is_master=True)
        LOG.info("Initial loading of the master config")
        master_source.refresh()
        if not master_source.get_config().get('standalone', False):
            Thread(target=reload_master_config, name="master_config_loader", daemon=True).start()


def reload_master_config():
    global master_source
    with open(os.path.join(master_source.get_path(), 'shared_config_manager.yaml')) as config_file:
        config = yaml.load(config_file)
        _handle_master_config(config)


def _handle_master_config(config: Mapping[str, Any]) -> None:
    global sources, filtered_sources
    if MASTER_ID in config['sources']:
        raise HTTPBadRequest(f'A source cannot have the "{MASTER_ID}" id')
    new_sources, filtered = _filter_sources(config['sources'])
    filtered_sources = {
        id_: _create_source(id_, config)
        for id_, config in filtered.items()
    }
    to_deletes = set(sources.keys()) - set(new_sources.keys())
    for to_delete in to_deletes:
        _delete_source(to_delete)
    errors = 0
    for id_, source_config in new_sources.items():
        prev_source = sources.get(id_)
        if prev_source is None:
            LOG.info("New source detected: %s", id_)
        elif prev_source.get_config() == source_config:
            LOG.debug("Source %s didn't change, not reloading it", id_)
            continue
        else:
            LOG.info("Change detected in source %s, reloading it", id_)
            _delete_source(id_)  # to be sure the old stuff is cleaned

        try:
            sources[id_] = _create_source(id_, source_config)
            sources[id_].refresh()
        except Exception:
            LOG.error("Cannot load the %s config", id_, exc_info=True)
            errors += 1
    _update_flag("READY" if errors == 0 else "ERROR")


def _update_flag(value):
    with open(os.path.join(tempfile.gettempdir(), 'status'), 'w') as flag:
        flag.write(value)


def _prepare_ssh():
    home = pathlib.Path.home()
    other_ssh = home.joinpath('.ssh2')
    if other_ssh.is_dir():
        ssh = home.joinpath('.ssh')
        subprocess.check_call(['rsync', '-a', str(other_ssh) + '/', str(ssh) + '/'])


def _delete_source(id_):
    global sources
    sources[id_].delete()
    del sources[id_]


def _filter_sources(source_configs):
    if TAG_FILTER is None:
        return source_configs, {}
    result = {}
    filtered = {}
    for id_, config in source_configs.items():
        if TAG_FILTER in config.get('tags', []):
            result[id_] = config
        else:
            filtered[id_] = config
    return result, filtered


@broadcast.decorator()
def refresh(id_, key):
    source, filtered = check_id_key(id_, key)
    if filtered:
        return
    LOG.info("Reloading the %s config", id_)
    source.refresh()
    if source.is_master() and not master_source.get_config().get('standalone', False):
        reload_master_config()


def check_id_key(id_, key):
    filtered = False
    source = get_source(id_)
    if source is None:
        source = filtered_sources.get(id_)
        filtered = True
    if source is not None:
        try:
            source.validate_key(key)
        except HTTPForbidden:
            master_source.validate_key(key)
        return source, filtered
    raise HTTPNotFound(f"Unknown id {id_}")


def get_source(id_) -> base.BaseSource:
    global master_source, sources
    if master_source.get_id() == id_:
        return master_source
    else:
        return sources.get(id_)


def get_stats():
    return {
        id_: source.get_stats()
        for id_, source in {**sources, master_source.get_id(): master_source}.items()
    }
