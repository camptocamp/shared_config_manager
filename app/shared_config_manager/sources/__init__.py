from c2cwsgiutils import broadcast
import logging
import os
from pyramid.httpexceptions import HTTPNotFound, HTTPBadRequest
import tempfile
from threading import Thread
from typing import Mapping
import yaml

from . import git, rsync, base

ENGINES = {
    'git': git.GitSource,
    'rsync': rsync.RsyncSource
}
LOG = logging.getLogger(__name__)
MASTER_ID = 'master'
master_source: base.BaseSource = None
sources: Mapping[str, base.BaseSource] = {}


def _create_source(id_, config, is_master=False):
    type_ = config['type']
    return ENGINES[type_](id_, config, is_master)


def init():
    global master_source
    _update_flag("LOADING")
    content = yaml.load(os.environ['MASTER_CONFIG'])
    master_source = _create_source(MASTER_ID, content, is_master=True)
    LOG.info("Initial loading of the master config")
    master_source.refresh()
    if not master_source.get_config().get('standalone', False):
        Thread(target=reload_master_config, name="master_config_loader", daemon=True).start()


def reload_master_config():
    global sources, master_source
    with open(os.path.join(master_source.get_path(), 'shared_config_manager.yaml')) as config_file:
        config = yaml.load(config_file)
        if MASTER_ID in config['sources']:
            raise HTTPBadRequest(f'A source cannot have the "{MASTER_ID}" id')
        to_deletes = set(sources.keys()) - set(config['sources'].keys())
        for to_delete in to_deletes:
            _delete_source(to_delete)
        for id_, source_config in config['sources'].items():
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
    _update_flag("READY")


def _update_flag(value):
    with open(os.path.join(tempfile.gettempdir(), 'status'), 'w') as flag:
        flag.write(value)


def _delete_source(id_):
    global sources
    sources[id_].delete()
    del sources[id_]


@broadcast.decorator()
def refresh(id_, key):
    config = check_id_key(id_, key)
    LOG.info("Reloading the %s config", id_)
    config.refresh()
    if config.is_master() and not master_source.get_config().get('standalone', False):
        reload_master_config()
    return True


def check_id_key(id_, key):
    source = get_source(id_)
    if source is None:
        raise HTTPNotFound(f"Unknown id {id_}")
    source.validate_key(key)
    return source


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
